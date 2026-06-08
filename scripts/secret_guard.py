#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import re
import subprocess
import sys
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_SCAN_BYTES = 2_000_000


_SECRET_NAME = r"[A-Za-z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD)"
_EXTENDED_SECRET_NAME = rf"{_SECRET_NAME}|[A-Za-z0-9_]*(?:SERVICE[_-]?KEY|CLIENT[_-]?SECRET)"
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    (
        "private-key",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE),
    ),
    (
        "secret-assignment",
        re.compile(
            rf"(?i)\b(?:{_EXTENDED_SECRET_NAME})\b\s*[:=]\s*['\"]?([A-Za-z0-9+/=_:.-]{{16,}})"
        ),
    ),
    (
        "secret-url-query",
        re.compile(
            rf"(?i)([?&](?:{_SECRET_NAME})=)([^&\s]{{12,}})"
        ),
    ),
]
_SAFE_PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "redacted",
    "your-",
    "your_",
    "changeme",
    "replace-me",
    "dummy",
    "${",
    "<",
    "[",
)


@dataclass(frozen=True)
class Finding:
    source: str
    line_number: int
    kind: str
    redacted_line: str

    def render(self) -> str:
        return f"{self.source}:{self.line_number}: {self.kind}: {self.redacted_line}"


def _run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _git_zsplit(output: bytes) -> list[str]:
    return [part.decode("utf-8", errors="replace") for part in output.split(b"\0") if part]


def _run_git_bytes(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=check, capture_output=True)


def _tracked_files() -> list[Path]:
    completed = _run_git_bytes(["ls-files", "-z"])
    return [REPO_ROOT / path for path in _git_zsplit(completed.stdout)]


def _staged_files() -> list[Path]:
    completed = _run_git_bytes(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT"])
    return [REPO_ROOT / path for path in _git_zsplit(completed.stdout)]


def _changed_files_for_commit(commit: str) -> list[str]:
    completed = _run_git_bytes(
        ["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--diff-filter=ACMRT", commit],
        check=False,
    )
    if completed.returncode != 0:
        return []
    return _git_zsplit(completed.stdout)


def _commits_in_range(rev_range: str) -> list[str]:
    completed = _run_git(["rev-list", "--reverse", rev_range], check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"Unable to enumerate range: {rev_range}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _blob_text(commit: str, path: str) -> str | None:
    completed = _run_git_bytes(["show", f"{commit}:{path}"], check=False)
    if completed.returncode != 0:
        return None
    content = completed.stdout[:MAX_SCAN_BYTES]
    if b"\0" in content:
        return None
    return content.decode("utf-8", errors="replace")


def _is_placeholder(value: str) -> bool:
    if value.startswith("_"):
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in _SAFE_PLACEHOLDER_MARKERS)


def _redact_line(line: str) -> str:
    redacted = line
    for kind, pattern in _SECRET_PATTERNS:
        if kind == "secret-assignment":
            redacted = pattern.sub(lambda match: match.group(0).replace(match.group(1), "[REDACTED]"), redacted)
        elif kind == "secret-url-query":
            redacted = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted.strip()


def _scan_text(source: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(line):
                if kind == "secret-assignment":
                    candidate = match.group(1)
                elif kind == "secret-url-query":
                    candidate = match.group(2)
                else:
                    candidate = match.group(0)
                if _is_placeholder(candidate):
                    continue
                findings.append(
                    Finding(
                        source=source,
                        line_number=line_number,
                        kind=kind,
                        redacted_line=_redact_line(line),
                    )
                )
    return findings


def scan_files(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_bytes()[:MAX_SCAN_BYTES]
        except OSError:
            continue
        if b"\0" in content:
            continue
        try:
            display = str(path.relative_to(REPO_ROOT))
        except ValueError:
            display = str(path)
        findings.extend(_scan_text(display, content.decode("utf-8", errors="replace")))
    return findings


def scan_range(rev_range: str) -> list[Finding]:
    findings: list[Finding] = []
    for commit in _commits_in_range(rev_range):
        for path in _changed_files_for_commit(commit):
            text = _blob_text(commit, path)
            if text is None:
                continue
            findings.extend(_scan_text(f"{path}@{commit[:12]}", text))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan repository content for likely committed secrets.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all-files", action="store_true", help="Scan all tracked files.")
    mode.add_argument("--staged", action="store_true", help="Scan staged files.")
    mode.add_argument("--range", dest="rev_range", help="Scan blobs changed in a git revision range.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.all_files:
        findings = scan_files(_tracked_files())
    elif args.staged:
        findings = scan_files(_staged_files())
    else:
        findings = scan_range(args.rev_range)

    if findings:
        print("Secret guard failed. Redacted findings:")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1

    print("Secret guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
