from __future__ import annotations

import json

from registry_scan_lib import (
    PRIMARY_ECOSYSTEMS,
    build_ecosystem_snapshot,
    build_secrets_manifest_metadata,
    parse_mcp_configs,
    user_home,
)


def test_user_home_is_absolute():
    home = user_home()
    assert home.is_absolute()


def test_primary_ecosystems_non_empty():
    assert len(PRIMARY_ECOSYSTEMS) >= 5


def test_build_ecosystem_snapshot_shape():
    config = PRIMARY_ECOSYSTEMS[0]
    snapshot = build_ecosystem_snapshot(config)
    assert snapshot["name"] == config.name
    assert "skills" in snapshot
    assert "hooks" in snapshot


def test_parse_mcp_configs_no_secret_values():
    result = parse_mcp_configs()
    serialized = json.dumps(result)
    for marker in ("sk-", "api_key", "password"):
        assert marker not in serialized.lower() or "has_plaintext_secret" in serialized
    assert "servers" in result
    assert "sources" in result


def test_secrets_manifest_metadata_shape():
    manifest = build_secrets_manifest_metadata()
    assert isinstance(manifest, list)
    assert len(manifest) > 0
    for entry in manifest:
        assert "secret_name" in entry
        assert "doppler_project" in entry
        assert "locations" in entry
        for location in entry["locations"]:
            assert "://" not in location  # no secret URLs leaked
