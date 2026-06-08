from __future__ import annotations

import json
from pathlib import Path

from generate_registry_dashboard import generate_dashboard


FIXTURE_SNAPSHOT = {
    "generated_at": "2026-06-08T00:00:00+00:00",
    "ecosystems": [
        {"id": 1, "name": "cursor", "type": "primary", "config_path": "/tmp/skills"},
    ],
    "ecosystem_name_by_local_id": {"1": "cursor"},
    "skills": [
        {
            "name": "Test Skill Alpha",
            "path": "/tmp/skills/alpha/SKILL.md",
            "tags": ["alpha", "test"],
            "source_of_truth": True,
            "ecosystem_ids": [1],
        }
    ],
    "mcp_servers": [
        {
            "name": "Test MCP",
            "command_or_url": "npx test-mcp",
            "ecosystem_sources": ["cursor"],
            "has_plaintext_secret": False,
            "metadata": {"sources": ["cursor"]},
        }
    ],
    "mcp_server_count": 1,
    "hooks": [
        {
            "ecosystem_id": 1,
            "event_type": "PostToolUse",
            "path": "/tmp/hooks.json",
            "action": "run",
        }
    ],
    "cli_tools": [{"name": "python", "available": True, "version": "3.11", "path": "/usr/bin/python"}],
    "secrets_manifest": [
        {
            "secret_name": "TEST_KEY",
            "doppler_project": "codingagents",
            "doppler_config": "dev",
            "locations": ["/tmp/mcp.json"],
        }
    ],
    "extra_surfaces": {
        "appdata_settings": [{"path": "/tmp/settings.json", "exists": True, "kind": "file"}]
    },
}


def test_dashboard_contains_skill_and_mcp_names(tmp_path: Path):
    snapshot_path = tmp_path / "registry_snapshot.json"
    output_path = tmp_path / "registry-dashboard.html"
    snapshot_path.write_text(json.dumps(FIXTURE_SNAPSHOT), encoding="utf-8")

    generate_dashboard(snapshot_path=snapshot_path, output_path=output_path)
    html = output_path.read_text(encoding="utf-8")

    assert "Test Skill Alpha" in html
    assert "Test MCP" in html
    assert "cursor" in html
    assert "TEST_KEY" in html
