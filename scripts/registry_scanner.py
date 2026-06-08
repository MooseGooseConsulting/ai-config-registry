#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import argparse
import json
import os
from urllib import error, parse, request

from registry_scan_lib import (
    CLI_TOOLS_TO_CHECK,
    PRIMARY_ECOSYSTEMS,
    VENDOR_CACHE_ECOSYSTEMS,
    build_ecosystem_snapshot,
    build_secrets_manifest_metadata,
    check_cli_tools,
    enumerate_extra_surfaces,
    parse_mcp_configs,
    sanitize_env_presence,
    utc_timestamp,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKING_DIR = REPO_ROOT / "working"
SNAPSHOT_PATH = WORKING_DIR / "registry_snapshot.json"
SUMMARY_PATH = WORKING_DIR / "registry_summary.md"
DEFAULT_SUPABASE_PROJECT_REF = "agookcvqnalxxcnhttmd"


def resolve_supabase_url() -> str | None:
    explicit = os.getenv("SUPABASE_URL")
    if explicit:
        return explicit.rstrip("/")
    if os.getenv("SUPABASE_SERVICE_KEY"):
        project_ref = os.getenv("SUPABASE_PROJECT_REF", DEFAULT_SUPABASE_PROJECT_REF)
        if project_ref:
            return f"https://{project_ref}.supabase.co"
    return None


def _now_human() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")


def build_snapshot() -> dict:
    ecosystems_raw = [
        build_ecosystem_snapshot(config)
        for config in [*PRIMARY_ECOSYSTEMS, *VENDOR_CACHE_ECOSYSTEMS]
    ]
    cli_tools = check_cli_tools(CLI_TOOLS_TO_CHECK)
    mcp = parse_mcp_configs()
    env_presence = sanitize_env_presence()
    extra_surfaces = enumerate_extra_surfaces()
    secrets_manifest = build_secrets_manifest_metadata()

    ecosystems = []
    skills = []
    hooks = []
    ecosystem_name_by_local_id: dict[int, str] = {}

    for idx, eco in enumerate(ecosystems_raw, start=1):
        ecosystem_name_by_local_id[idx] = eco["name"]
        ecosystems.append(
            {
                "id": idx,
                "name": eco["name"],
                "config_path": eco["skills_path"],
                "type": "vendor-cache" if not eco["source_of_truth"] else "primary",
            }
        )
        for skill in eco["skills"]:
            skills.append(
                {
                    "name": skill["name"],
                    "path": skill["path"],
                    "description": skill.get("description", ""),
                    "tags": skill.get("tags", []),
                    "source_of_truth": eco["source_of_truth"],
                    "ecosystem_ids": [idx],
                }
            )
        for hook_path in eco["hooks"]:
            hooks.append(
                {
                    "ecosystem_id": idx,
                    "event_type": "unknown",
                    "path": hook_path,
                    "action": "catalogued",
                }
            )

    mcp_servers = []
    for server in mcp["servers"]:
        ecosystem_sources = server.get("ecosystem_sources", [])
        mcp_servers.append(
            {
                "name": server["name"],
                "command_or_url": server.get("command_or_url", ""),
                "ecosystem_ids": [],
                "ecosystem_sources": ecosystem_sources,
                "has_plaintext_secret": server.get("has_plaintext_secret", False),
                "doppler_key": server.get("doppler_key"),
                "metadata": server.get("metadata", {}),
            }
        )

    return {
        "generated_at": utc_timestamp(),
        "machine": {"os": os.name},
        "ecosystems": ecosystems,
        "ecosystem_name_by_local_id": ecosystem_name_by_local_id,
        "skills": skills,
        "mcp_servers": mcp_servers,
        "mcp_sources": mcp["sources"],
        "mcp_server_count": mcp["server_count"],
        "hooks": hooks,
        "secrets_manifest": secrets_manifest,
        "cli_tools": cli_tools,
        "extra_surfaces": extra_surfaces,
        "supabase_env_present": env_presence,
    }


def write_artifacts(snapshot: dict) -> None:
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(build_summary_markdown(snapshot), encoding="utf-8")


def build_summary_markdown(snapshot: dict) -> str:
    ecosystem_lines = []
    for eco in snapshot["ecosystems"]:
        ecosystem_lines.append(
            f"- `{eco['name']}`: type={eco.get('type', 'unknown')} path={eco.get('config_path', '')}"
        )

    mcp_sources_lines = []
    for source_name, details in snapshot["mcp_sources"].items():
        details_suffix = ""
        if source_name == "omc_registry" and "top_level_keys" in details:
            details_suffix = f" keys={len(details['top_level_keys'])}"
        mcp_sources_lines.append(
            f"- `{source_name}`: status={details.get('status', 'unknown')}{details_suffix}"
        )

    cli_lines = [
        f"- `{tool['name']}`: {'available' if tool['available'] else 'missing'}" for tool in snapshot["cli_tools"]
    ]
    extra_lines = []
    for surface_name, entries in snapshot["extra_surfaces"].items():
        if isinstance(entries, list):
            found = len([entry for entry in entries if entry.get("exists")])
            extra_lines.append(f"- `{surface_name}`: {found}/{len(entries)} paths present")
        elif isinstance(entries, dict):
            extra_lines.append(f"- `{surface_name}`: captured")

    return "\n".join(
        [
            "# Registry Summary",
            "",
            f"Generated: `{_now_human()}`",
            "",
            "## Ecosystems",
            *ecosystem_lines,
            "",
            "## MCP Sources",
            *mcp_sources_lines,
            "",
            f"Unique MCP servers discovered: `{snapshot['mcp_server_count']}`",
            "",
            "## CLI Tool Inventory",
            *cli_lines,
            "",
            "## Additional Enumeration Surfaces",
            *extra_lines,
            "",
            "## Supabase Mode",
            "- Optional upsert enabled only when `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are present.",
            f"- Env presence: `{snapshot['supabase_env_present']}`",
            "",
            "## Artifacts",
            f"- `{SNAPSHOT_PATH}`",
            f"- `{SUMMARY_PATH}`",
            "",
        ]
    )


def _supabase_headers(service_key: str, *, on_conflict: str | None = None) -> dict[str, str]:
    prefer = "resolution=merge-duplicates,return=minimal"
    if on_conflict:
        prefer = f"{prefer},on_conflict={on_conflict}"
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _assert_https_url(url: str) -> None:
    parsed = parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Refusing non-HTTPS Supabase URL: {url}")


def _post_json(
    url: str,
    payload: list[dict] | dict,
    headers: dict[str, str],
) -> tuple[bool, str]:
    _assert_https_url(url)
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30):
            return True, "ok"
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return False, f"http_error:{exc.code}:{body}"
    except Exception as exc:  # pragma: no cover - network variability
        return False, f"request_error:{exc.__class__.__name__}"


def _get_json(url: str, headers: dict[str, str]) -> tuple[bool, Any, str]:
    _assert_https_url(url)
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=30) as response:
            return True, json.loads(response.read().decode("utf-8")), "ok"
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return False, None, f"http_error:{exc.code}:{body}"
    except Exception as exc:  # pragma: no cover - network variability
        return False, None, f"request_error:{exc.__class__.__name__}"


def _ecosystem_rows_for_upsert(snapshot: dict) -> list[dict]:
    return [
        {
            "name": eco["name"],
            "config_path": eco.get("config_path"),
            "type": eco.get("type"),
        }
        for eco in snapshot["ecosystems"]
    ]


def _fetch_ecosystem_id_map(base_url: str, service_key: str) -> tuple[bool, dict[str, int], str]:
    headers = _supabase_headers(service_key)
    endpoint = f"{base_url}/ecosystems?select=id,name"
    ok, payload, status = _get_json(endpoint, headers)
    if not ok or not isinstance(payload, list):
        return False, {}, status

    mapping = {row["name"]: int(row["id"]) for row in payload if "name" in row and "id" in row}
    return True, mapping, "ok"


def sanitize_secrets_manifest_for_remote(
    manifest: list[dict], *, include_secret_locations: bool
) -> list[dict]:
    sanitized: list[dict] = []
    for entry in manifest:
        row = {
            "secret_name": entry.get("secret_name"),
            "doppler_project": entry.get("doppler_project", "codingagents"),
            "doppler_config": entry.get("doppler_config", "dev"),
            "locations": entry.get("locations", []) if include_secret_locations else [],
        }
        sanitized.append(row)
    return sanitized


def remap_ecosystem_ids(
    snapshot: dict,
    name_to_db_id: dict[str, int],
    *,
    include_secret_locations: bool = False,
) -> dict[str, list[dict]]:
    local_to_name = snapshot.get("ecosystem_name_by_local_id") or {
        eco["id"]: eco["name"] for eco in snapshot["ecosystems"]
    }

    def remap_ids(local_ids: list[int]) -> list[int]:
        remapped: list[int] = []
        for local_id in local_ids:
            name = local_to_name.get(local_id)
            if name and name in name_to_db_id:
                remapped.append(name_to_db_id[name])
        return remapped

    skills = []
    for skill in snapshot["skills"]:
        skills.append(
            {
                "name": skill["name"],
                "path": skill["path"],
                "description": skill.get("description", ""),
                "tags": skill.get("tags", []),
                "source_of_truth": skill.get("source_of_truth", False),
                "ecosystem_ids": remap_ids(skill.get("ecosystem_ids", [])),
            }
        )

    hooks = []
    for hook in snapshot["hooks"]:
        local_id = hook.get("ecosystem_id")
        db_id = None
        if local_id is not None:
            name = local_to_name.get(local_id)
            if name:
                db_id = name_to_db_id.get(name)
        hooks.append(
            {
                "ecosystem_id": db_id,
                "event_type": hook.get("event_type", "unknown"),
                "path": hook.get("path"),
                "action": hook.get("action"),
            }
        )

    mcp_servers = []
    for server in snapshot["mcp_servers"]:
        mcp_servers.append(
            {
                "name": server["name"],
                "command_or_url": server.get("command_or_url") or "",
                "ecosystem_ids": [],
                "has_plaintext_secret": server.get("has_plaintext_secret", False),
                "doppler_key": server.get("doppler_key"),
                "metadata": server.get("metadata", {}),
            }
        )

    secrets_manifest = sanitize_secrets_manifest_for_remote(
        snapshot["secrets_manifest"],
        include_secret_locations=include_secret_locations,
    )
    cli_rows = [
        {
            "name": tool["name"],
            "installed": tool["available"],
            "version": tool.get("version", ""),
            "path": tool.get("path"),
        }
        for tool in snapshot["cli_tools"]
    ]

    return {
        "skills": skills,
        "hooks": hooks,
        "mcp_servers": mcp_servers,
        "secrets_manifest": secrets_manifest,
        "cli_tools": cli_rows,
    }


def maybe_supabase_upsert(snapshot: dict, *, include_secret_locations: bool = False) -> dict[str, str]:
    supabase_url = resolve_supabase_url()
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not supabase_url or not service_key:
        return {"status": "skipped", "reason": "missing_env"}

    base_url = supabase_url.rstrip("/") + "/rest/v1"
    result: dict[str, str] = {"status": "attempted"}

    eco_payload = _ecosystem_rows_for_upsert(snapshot)
    eco_endpoint = f"{base_url}/ecosystems?on_conflict=name"
    ok, status = _post_json(eco_endpoint, eco_payload, _supabase_headers(service_key, on_conflict="name"))
    result["ecosystems"] = status if ok else f"failed:{status}"
    if not ok:
        result["status"] = "failed"
        return result

    ok, name_to_db_id, fetch_status = _fetch_ecosystem_id_map(base_url, service_key)
    result["ecosystem_id_map"] = fetch_status if ok else f"failed:{fetch_status}"
    if not ok:
        result["status"] = "failed"
        return result

    rows = remap_ecosystem_ids(
        snapshot,
        name_to_db_id,
        include_secret_locations=include_secret_locations,
    )
    table_specs = [
        ("skills", "path"),
        ("mcp_servers", "name,command_or_url"),
        ("hooks", "ecosystem_id,path"),
        ("secrets_manifest", "secret_name"),
        ("cli_tools", "name"),
    ]

    for table, conflict in table_specs:
        payload = rows[table]
        if not payload:
            result[table] = "skipped_empty"
            continue
        endpoint = f"{base_url}/{parse.quote(table)}?on_conflict={parse.quote(conflict)}"
        table_ok, table_status = _post_json(
            endpoint,
            payload,
            _supabase_headers(service_key, on_conflict=conflict),
        )
        result[table] = table_status if table_ok else f"failed:{table_status}"
        if not table_ok:
            result["status"] = "failed"

    if result.get("status") != "failed":
        result["status"] = "ok"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan local AI configuration registry surfaces.")
    parser.add_argument(
        "--upsert-supabase",
        action="store_true",
        help="Attempt Supabase upsert when SUPABASE_URL and SUPABASE_SERVICE_KEY are present.",
    )
    parser.add_argument(
        "--include-secret-locations",
        action="store_true",
        help="Upload file paths in secrets_manifest to Supabase (off by default; see docs/SECURITY.md).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    snapshot = build_snapshot()
    if args.upsert_supabase:
        snapshot["supabase_upsert"] = maybe_supabase_upsert(
            snapshot,
            include_secret_locations=args.include_secret_locations,
        )
    else:
        snapshot["supabase_upsert"] = {"status": "disabled"}

    write_artifacts(snapshot)

    print(f"[registry-scanner] Wrote: {SNAPSHOT_PATH}")
    print(f"[registry-scanner] Wrote: {SUMMARY_PATH}")
    upsert = snapshot["supabase_upsert"]
    print(f"[registry-scanner] Supabase mode: {upsert.get('status')}")
    if upsert.get("status") in {"attempted", "ok", "failed"}:
        for key, value in upsert.items():
            if key != "status":
                print(f"[registry-scanner]   {key}: {value}")

    if upsert.get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
