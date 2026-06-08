from __future__ import annotations

from registry_scanner import remap_ecosystem_ids


def test_remap_ecosystem_ids_rewrites_foreign_keys():
    snapshot = {
        "ecosystems": [
            {"id": 1, "name": "cursor", "type": "primary"},
            {"id": 2, "name": "codex", "type": "primary"},
        ],
        "ecosystem_name_by_local_id": {1: "cursor", 2: "codex"},
        "skills": [
            {
                "name": "Skill A",
                "path": "/a/SKILL.md",
                "description": "",
                "tags": [],
                "source_of_truth": True,
                "ecosystem_ids": [1, 2],
            }
        ],
        "hooks": [
            {"ecosystem_id": 2, "event_type": "unknown", "path": "/hooks.json", "action": "catalogued"}
        ],
        "mcp_servers": [
            {
                "name": "MCP",
                "command_or_url": "cmd",
                "ecosystem_sources": ["cursor"],
                "has_plaintext_secret": False,
                "doppler_key": None,
                "metadata": {},
            }
        ],
        "secrets_manifest": [],
        "cli_tools": [{"name": "python", "available": True, "version": "", "path": "/bin/python"}],
    }

    name_to_db_id = {"cursor": 101, "codex": 202}
    rows = remap_ecosystem_ids(snapshot, name_to_db_id)

    assert rows["skills"][0]["ecosystem_ids"] == [101, 202]
    assert rows["hooks"][0]["ecosystem_id"] == 202
    assert rows["mcp_servers"][0]["name"] == "MCP"
    assert "id" not in rows["skills"][0]
