"""Security-related upsert sanitization tests."""

from registry_scanner import sanitize_secrets_manifest_for_remote


def test_secrets_manifest_strips_locations_by_default():
    manifest = [
        {
            "secret_name": "MORPH_API_KEY",
            "doppler_project": "codingagents",
            "doppler_config": "dev",
            "locations": ["/home/example/.cursor/mcp.json"],
        }
    ]
    result = sanitize_secrets_manifest_for_remote(manifest, include_secret_locations=False)
    assert result[0]["locations"] == []
    assert result[0]["secret_name"] == "MORPH_API_KEY"


def test_secrets_manifest_includes_locations_when_opted_in():
    manifest = [
        {
            "secret_name": "MORPH_API_KEY",
            "doppler_project": "codingagents",
            "doppler_config": "dev",
            "locations": ["/home/example/.cursor/mcp.json"],
        }
    ]
    result = sanitize_secrets_manifest_for_remote(manifest, include_secret_locations=True)
    assert result[0]["locations"] == ["/home/example/.cursor/mcp.json"]
