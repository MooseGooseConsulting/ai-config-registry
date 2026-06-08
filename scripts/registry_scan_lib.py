from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tomllib
from typing import Any


def user_home() -> Path:
    profile = os.environ.get("USERPROFILE")
    if profile:
        return Path(profile)
    return Path.home()


HOME = user_home()


@dataclass(frozen=True)
class EcosystemConfig:
    name: str
    skills_path: Path
    source_of_truth: bool = True


PRIMARY_ECOSYSTEMS: list[EcosystemConfig] = [
    EcosystemConfig("agents", HOME / ".agents" / "skills", True),
    EcosystemConfig("cursor", HOME / ".cursor" / "skills-cursor", True),
    EcosystemConfig("codex", HOME / ".codex" / "skills", True),
    EcosystemConfig("claude", HOME / ".claude" / "skills", True),
    EcosystemConfig("gemini", HOME / ".gemini" / "skills", True),
    EcosystemConfig("kilo", HOME / ".kilo" / "skills", True),
    EcosystemConfig("copilot", HOME / ".copilot" / "skills", True),
    EcosystemConfig("kimiclaw", HOME / "Downloads" / "KimiClaw" / "skills", True),
    EcosystemConfig("downloads-skills", HOME / "Downloads" / "skills", True),
]


VENDOR_CACHE_ECOSYSTEMS: list[EcosystemConfig] = [
    EcosystemConfig("cursor-vendor-cache", HOME / ".cursor" / "plugins" / "cache", False),
    EcosystemConfig("claude-vendor-cache", HOME / ".claude" / "plugins" / "cache", False),
    EcosystemConfig("gemini-vendor-cache", HOME / ".gemini" / "plugins" / "cache", False),
    EcosystemConfig("copilot-vendor-cache", HOME / ".copilot" / "plugins" / "cache", False),
]


MCP_INPUT_PATHS: dict[str, Path] = {
    "cursor": HOME / ".cursor" / "mcp.json",
    "codex_toml": HOME / ".codex" / "config.toml",
    "claude_json": HOME / ".claude.json",
    "claude_mcp": HOME / ".claude" / "mcp.json",
    "gemini_antigravity": HOME / ".gemini" / "antigravity" / "mcp_config.json",
    "omc_registry": HOME / ".omc" / "mcp-registry.json",
}

MCP_SOURCE_LABELS: dict[str, str] = {
    "cursor": "cursor",
    "codex_toml": "codex",
    "claude_json": "claude",
    "claude_mcp": "claude",
    "gemini_antigravity": "gemini",
    "omc_registry": "omc",
}


CLI_TOOLS_TO_CHECK: list[str] = [
    "claude",
    "codex",
    "gemini",
    "kimi",
    "cursor",
    "goose",
    "amp",
    "opencode",
    "aider",
    "continue",
    "roo",
    "notebooklm-mcp",
    "pieces",
    "tavily",
    "exa",
    "supabase",
    "doppler",
    "morph-mcp",
    "nlm",
    "uv",
    "pipx",
    "pip",
    "python",
    "npm",
]

EXTRA_SURFACES: dict[str, list[Path]] = {
    "appdata_settings": [
        HOME / "AppData" / "Roaming" / "Code - Insiders" / "User" / "settings.json",
        HOME / "AppData" / "Roaming" / "Cursor" / "User" / "settings.json",
    ],
    "shell_profiles": [
        HOME / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
        HOME / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
        HOME / ".bashrc",
        HOME / ".zshrc",
        HOME
        / "AppData"
        / "Local"
        / "Packages"
        / "CanonicalGroupLimited.UbuntuonWindows_79rhkp1fndgsc"
        / "LocalState"
        / "rootfs"
        / "home"
        / "pmacl"
        / ".bashrc",
        HOME
        / "AppData"
        / "Local"
        / "Packages"
        / "CanonicalGroupLimited.UbuntuonWindows_79rhkp1fndgsc"
        / "LocalState"
        / "rootfs"
        / "home"
        / "pmacl"
        / ".zshrc",
    ],
    "transcript_and_cache_metadata": [
        HOME / ".cursor" / "projects",
        HOME / ".codex" / "logs",
        HOME / ".claude" / "projects",
        HOME / ".doppler" / "fallback",
        HOME / ".omc" / "state",
    ],
}

KNOWN_SECRET_KEYS = [
    "MORPH_API_KEY",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
    "CONTEXT7_API_KEY",
    "STITCH_GOOGLE_API_KEY",
    "GITHUB_PERSONAL_ACCESS_TOKEN",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "SUPABASE_SERVICE_KEY",
    "APIFY_TOKEN",
    "PLAID_CLIENT_ID",
    "PLAID_SECRET",
]

_PLAINTEXT_SECRET_PATTERNS = [
    re.compile(r'"[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)"\s*:\s*"(?!\$\{)[^"]{8,}"'),
    re.compile(r'=\s*"(?!\$\{)[A-Za-z0-9+/=_-]{12,}"'),
]
_REDACT_URL_QUERY = re.compile(
    r"([?&](?:[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)|exaApiKey)=)([^&\s]+)",
    re.IGNORECASE,
)


def redact_sensitive_text(value: str) -> str:
    if not value:
        return value
    redacted = _REDACT_URL_QUERY.sub(r"\1[REDACTED]", value)
    for key in KNOWN_SECRET_KEYS:
        redacted = re.sub(
            rf"({re.escape(key)}\s*[=:]\s*)(?!\$\{{)[^\s\"']+",
            r"\1[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def safe_read_json(path: Path) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # pragma: no cover - defensive parse layer
        return None, f"parse_error: {exc}"


def safe_read_toml(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # pragma: no cover - defensive parse layer
        return None, f"parse_error: {exc}"


def discover_skills(base_path: Path) -> list[dict[str, Any]]:
    if not base_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for skill_md in sorted(base_path.rglob("SKILL.md")):
        try:
            skill_dir = skill_md.parent
            title = skill_dir.name
            description = ""
            tags: list[str] = []
            text = skill_md.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line.removeprefix("# ").strip() or title
                    break
            parts = [p.lower() for p in skill_md.relative_to(base_path).parts]
            tags = sorted({p for p in parts if p not in {"skill.md", "skills"}})
            nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
            if nonempty_lines:
                description = nonempty_lines[1] if len(nonempty_lines) > 1 else nonempty_lines[0]
            records.append(
                {
                    "name": title,
                    "path": str(skill_md),
                    "relative_path": str(skill_md.relative_to(base_path)),
                    "size_bytes": skill_md.stat().st_size,
                    "description": description[:280],
                    "tags": tags[:20],
                }
            )
        except OSError:
            continue
    return records


def discover_agents_docs(base_path: Path) -> list[str]:
    if not base_path.exists():
        return []
    return [str(path) for path in sorted(base_path.rglob("AGENTS.md"))]


def discover_hook_files(base_path: Path) -> list[str]:
    if not base_path.exists():
        return []
    patterns = ("hooks.json", "hooks.yaml", "hooks.yml")
    matches: list[str] = []
    for pattern in patterns:
        for match in sorted(base_path.rglob(pattern)):
            matches.append(str(match))
    return matches


def _run_capture(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        return (completed.stdout or completed.stderr or "").strip()
    except Exception:
        return ""


def check_cli_tools(tools: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tool in tools:
        resolved = shutil.which(tool)
        version_output = ""
        if resolved:
            version_output = _run_capture([resolved, "--version"]) or _run_capture([resolved, "-v"])
        results.append(
            {
                "name": tool,
                "available": bool(resolved),
                "path": resolved,
                "version": version_output.splitlines()[0][:120] if version_output else "",
            }
        )
    return results


def build_ecosystem_snapshot(config: EcosystemConfig) -> dict[str, Any]:
    skills = discover_skills(config.skills_path)
    agents_docs = discover_agents_docs(config.skills_path)
    hooks = discover_hook_files(config.skills_path)

    return {
        "name": config.name,
        "skills_path": str(config.skills_path),
        "exists": config.skills_path.exists(),
        "source_of_truth": config.source_of_truth,
        "skill_count": len(skills),
        "skills": skills,
        "agents_docs": agents_docs,
        "hooks": hooks,
    }


def _extract_key_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(value.keys())
    return []


def _command_or_url_from_config(config: Any) -> str:
    if not isinstance(config, dict):
        return ""
    if config.get("url"):
        return str(config["url"])
    command = config.get("command")
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    if command:
        return str(command)
    return ""


def _has_plaintext_secret(config: Any, raw_text: str = "") -> bool:
    if isinstance(config, dict):
        env = config.get("env")
        if isinstance(env, dict):
            for value in env.values():
                text = str(value)
                if text and not text.startswith("${") and len(text) >= 8:
                    return True
    for pattern in _PLAINTEXT_SECRET_PATTERNS:
        if pattern.search(raw_text):
            return True
    return False


def _merge_server_record(
    records: dict[str, dict[str, Any]],
    name: str,
    source_key: str,
    config: Any,
    raw_text: str = "",
) -> None:
    command_or_url = redact_sensitive_text(_command_or_url_from_config(config))
    has_secret = _has_plaintext_secret(config, raw_text)
    ecosystem_label = MCP_SOURCE_LABELS.get(source_key, source_key)

    if name not in records:
        records[name] = {
            "name": name,
            "command_or_url": command_or_url,
            "ecosystem_sources": [],
            "has_plaintext_secret": has_secret,
            "doppler_key": None,
            "metadata": {},
        }
    else:
        existing = records[name]
        if not existing["command_or_url"] and command_or_url:
            existing["command_or_url"] = command_or_url
        existing["has_plaintext_secret"] = existing["has_plaintext_secret"] or has_secret

    if ecosystem_label not in records[name]["ecosystem_sources"]:
        records[name]["ecosystem_sources"].append(ecosystem_label)


def _ingest_server_section(
    records: dict[str, dict[str, Any]],
    section: Any,
    source_key: str,
    raw_text: str = "",
) -> None:
    if not isinstance(section, dict):
        return
    for name, config in section.items():
        _merge_server_record(records, str(name), source_key, config, raw_text)


def parse_mcp_configs() -> dict[str, Any]:
    result: dict[str, Any] = {"sources": {}, "servers": []}
    server_records: dict[str, dict[str, Any]] = {}

    cursor_path = MCP_INPUT_PATHS["cursor"]
    cursor_json, cursor_err = safe_read_json(cursor_path)
    cursor_raw = cursor_path.read_text(encoding="utf-8", errors="ignore") if cursor_path.exists() else ""
    result["sources"]["cursor"] = {
        "path": str(cursor_path),
        "status": "ok" if cursor_err is None else cursor_err,
    }
    if isinstance(cursor_json, dict):
        servers = cursor_json.get("mcpServers") or cursor_json.get("servers") or {}
        _ingest_server_section(server_records, servers, "cursor", cursor_raw)

    codex_path = MCP_INPUT_PATHS["codex_toml"]
    codex_toml, codex_err = safe_read_toml(codex_path)
    codex_raw = codex_path.read_text(encoding="utf-8", errors="ignore") if codex_path.exists() else ""
    result["sources"]["codex_toml"] = {
        "path": str(codex_path),
        "status": "ok" if codex_err is None else codex_err,
    }
    if isinstance(codex_toml, dict):
        mcp_servers = codex_toml.get("mcp_servers")
        _ingest_server_section(server_records, mcp_servers, "codex_toml", codex_raw)

    claude_json_path = MCP_INPUT_PATHS["claude_json"]
    claude_json, claude_err = safe_read_json(claude_json_path)
    claude_raw = claude_json_path.read_text(encoding="utf-8", errors="ignore") if claude_json_path.exists() else ""
    result["sources"]["claude_json"] = {
        "path": str(claude_json_path),
        "status": "ok" if claude_err is None else claude_err,
    }
    if isinstance(claude_json, dict):
        for candidate in ("mcpServers", "mcp_servers", "servers"):
            _ingest_server_section(server_records, claude_json.get(candidate), "claude_json", claude_raw)

    claude_mcp_path = MCP_INPUT_PATHS["claude_mcp"]
    claude_mcp, claude_mcp_err = safe_read_json(claude_mcp_path)
    claude_mcp_raw = claude_mcp_path.read_text(encoding="utf-8", errors="ignore") if claude_mcp_path.exists() else ""
    result["sources"]["claude_mcp"] = {
        "path": str(claude_mcp_path),
        "status": "ok" if claude_mcp_err is None else claude_mcp_err,
    }
    if isinstance(claude_mcp, dict):
        for candidate in ("mcpServers", "mcp_servers", "servers"):
            _ingest_server_section(server_records, claude_mcp.get(candidate), "claude_mcp", claude_mcp_raw)

    gemini_path = MCP_INPUT_PATHS["gemini_antigravity"]
    gemini_json, gemini_err = safe_read_json(gemini_path)
    gemini_raw = gemini_path.read_text(encoding="utf-8", errors="ignore") if gemini_path.exists() else ""
    result["sources"]["gemini_antigravity"] = {
        "path": str(gemini_path),
        "status": "ok" if gemini_err is None else gemini_err,
    }
    if isinstance(gemini_json, dict):
        for candidate in ("mcpServers", "mcp_servers", "servers"):
            _ingest_server_section(server_records, gemini_json.get(candidate), "gemini_antigravity", gemini_raw)

    omc_path = MCP_INPUT_PATHS["omc_registry"]
    omc_json, omc_err = safe_read_json(omc_path)
    omc_raw = omc_path.read_text(encoding="utf-8", errors="ignore") if omc_path.exists() else ""
    result["sources"]["omc_registry"] = {
        "path": str(omc_path),
        "status": "ok" if omc_err is None else omc_err,
        "sensitive": True,
    }
    if isinstance(omc_json, dict):
        omc_keys = sorted(omc_json.keys())
        result["sources"]["omc_registry"]["top_level_keys"] = omc_keys
        _ingest_server_section(server_records, omc_json, "omc_registry", omc_raw)

    result["servers"] = [
        {
            "name": record["name"],
            "command_or_url": record["command_or_url"],
            "ecosystem_sources": record["ecosystem_sources"],
            "has_plaintext_secret": record["has_plaintext_secret"],
            "doppler_key": record["doppler_key"],
            "metadata": {
                "sources": record["ecosystem_sources"],
            },
        }
        for record in sorted(server_records.values(), key=lambda item: item["name"].lower())
    ]
    result["server_count"] = len(result["servers"])
    return result


def _surface_kind(path: Path) -> str:
    if not path.exists():
        if path.name == "logs" and path.parent.name == ".codex":
            return "directory-or-missing"
        return "missing"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "unknown"


def enumerate_extra_surfaces() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, paths in EXTRA_SURFACES.items():
        entries: list[dict[str, Any]] = []
        for path in paths:
            entries.append(
                {
                    "path": str(path),
                    "exists": path.exists(),
                    "kind": _surface_kind(path),
                }
            )
        result[name] = entries

    npm_global = _run_capture(["npm", "-g", "list", "--depth=0"])
    pipx_list = _run_capture(["pipx", "list"])
    uv_tool_list = _run_capture(["uv", "tool", "list"])
    pip_list = _run_capture(["pip", "list"])
    if not pip_list and shutil.which("python"):
        pip_list = _run_capture(["python", "-m", "pip", "list"])
    result["global_runtime_inventory"] = {
        "npm_global": npm_global.splitlines()[:80],
        "pipx_list": pipx_list.splitlines()[:80],
        "uv_tool_list": uv_tool_list.splitlines()[:80],
        "pip_list": pip_list.splitlines()[:80],
    }
    return result


def build_secrets_manifest_metadata() -> list[dict[str, Any]]:
    secret_locations: dict[str, set[str]] = {key: set() for key in KNOWN_SECRET_KEYS}
    target_files = [path for path in MCP_INPUT_PATHS.values() if path.exists()]
    for file_path in target_files:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        for key in KNOWN_SECRET_KEYS:
            if re.search(rf"\b{re.escape(key)}\b", raw):
                secret_locations[key].add(str(file_path))

    return [
        {
            "secret_name": key,
            "doppler_project": "codingagents",
            "doppler_config": "dev",
            "locations": sorted(secret_locations[key]),
        }
        for key in KNOWN_SECRET_KEYS
    ]


def sanitize_env_presence() -> dict[str, bool]:
    has_key = bool(os.getenv("SUPABASE_SERVICE_KEY"))
    has_url = bool(os.getenv("SUPABASE_URL")) or has_key
    return {
        "SUPABASE_URL": has_url,
        "SUPABASE_SERVICE_KEY": has_key,
    }
