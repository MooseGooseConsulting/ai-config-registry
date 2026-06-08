from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_doppler_manifest_v2_is_public_safe():
    manifest = json.loads(_repo_text("working/doppler-migration-manifest.json"))
    serialized = json.dumps(manifest)
    old_local_user = "pm" + "acl"

    assert manifest["manifest_version"] == 2
    assert "source_catalog" in manifest
    assert "C:" + "/Users/" not in serialized
    assert old_local_user not in serialized

    for entry in manifest["secrets"]:
        assert "doppler_key" in entry
        assert "source_refs" in entry
        assert "source_paths" not in entry
        assert entry["source_refs"]


def test_doppler_scripts_use_manifest_and_do_not_pass_secret_values_on_argv():
    push_script = _repo_text("scripts/doppler-push-secrets.ps1")
    check_script = _repo_text("scripts/check-doppler-state.ps1")
    manifest_helper = _repo_text("scripts/doppler-manifest.ps1")
    push_contract = push_script + manifest_helper
    check_contract = check_script + manifest_helper

    assert "source_refs" in push_contract
    assert "source_paths" in push_contract  # v1 compatibility
    assert "$key=$plainValue" not in push_script
    assert "$key = $Key" not in push_script
    assert "secrets set $Key" in push_script
    assert "--silent" in push_script

    assert "ManifestPath" in check_script
    assert "source_refs" in check_contract
    assert "MORPH_API_KEY" not in check_script


def test_sync_supabase_upsert_fails_closed_without_unsafe_override():
    sync_script = _repo_text("scripts/sync-registry.ps1")

    assert "AllowUnsafeSupabaseUpsert" in sync_script
    assert "Invoke-SupabaseSecurityVerification" in sync_script
    assert "verify_supabase_security.ps1" in sync_script
    assert "unsafe override" in sync_script.lower()


def test_sync_supabase_upsert_uses_manifest_doppler_target():
    sync_script = _repo_text("scripts/sync-registry.ps1")

    assert "Resolve-DopplerManifestTarget" in sync_script
    assert "DopplerProject" in sync_script
    assert "DopplerConfig" in sync_script
    assert "--project codingagents --config dev" not in sync_script


def test_verify_supabase_security_is_strict_by_default_with_schema_only_escape_hatch():
    verify_script = _repo_text("scripts/verify_supabase_security.ps1")

    assert "[switch]$SchemaOnly" in verify_script
    assert "anon key denial" in verify_script.lower()
    assert "cannot complete strict verification" in verify_script.lower()
    assert "Supabase CLI is required" in verify_script
    assert "exit 1" in verify_script


def test_verify_supabase_security_captures_cli_exit_codes_before_out_string():
    verify_script = _repo_text("scripts/verify_supabase_security.ps1")

    assert "$rlsQueryExitCode = $LASTEXITCODE" in verify_script
    assert "$grantQueryExitCode = $LASTEXITCODE" in verify_script
    assert "if ($rlsQueryExitCode -ne 0)" in verify_script
    assert "if ($grantQueryExitCode -ne 0)" in verify_script


def test_secret_guard_exists_and_redacts_findings(tmp_path: Path):
    import sys

    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from secret_guard import scan_files

    token = "ghp_" + ("A" * 36)
    target = tmp_path / "leak.txt"
    target.write_text(f"GITHUB_PERSONAL_ACCESS_TOKEN={token}\n", encoding="utf-8")

    findings = scan_files([target])

    assert findings
    rendered = findings[0].render()
    assert token not in rendered
    assert "[REDACTED]" in rendered


def test_secret_guard_does_not_treat_test_substring_as_placeholder(tmp_path: Path):
    import sys

    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from secret_guard import scan_files

    target = tmp_path / "leak.py"
    leak_value = "prod_" + "test_supersecretvalue12345"
    target.write_text(f'MY_API_KEY = "{leak_value}"\n', encoding="utf-8")

    findings = scan_files([target])

    assert findings
    assert leak_value not in findings[0].render()


def test_secret_guard_uses_url_query_value_for_placeholder_filter(tmp_path: Path):
    import sys

    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from secret_guard import scan_files

    target = tmp_path / "example.md"
    target.write_text(
        "https://example.invalid/callback?api_token=REDACTED_TOKEN_VALUE\n",
        encoding="utf-8",
    )

    assert scan_files([target]) == []


def test_wsl_profile_discovery_uses_discovered_users(tmp_path: Path):
    import sys

    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from registry_scan_lib import discover_wsl_profile_paths
    old_local_user = "pm" + "acl"

    distro_root = (
        tmp_path
        / "AppData"
        / "Local"
        / "Packages"
        / "CanonicalGroupLimited.UbuntuonWindows_79rhkp1fndgsc"
        / "LocalState"
        / "rootfs"
        / "home"
        / "alice"
    )
    distro_root.mkdir(parents=True)
    (distro_root / ".bashrc").write_text("# bash\n", encoding="utf-8")
    (distro_root / ".zshrc").write_text("# zsh\n", encoding="utf-8")

    discovered = discover_wsl_profile_paths(tmp_path)

    assert distro_root / ".bashrc" in discovered
    assert distro_root / ".zshrc" in discovered
    assert all(f"rootfs/home/{old_local_user}" not in path.as_posix() for path in discovered)


@pytest.mark.parametrize(
    "workflow",
    [
        ".github/workflows/ci.yml",
        ".github/workflows/security-scan-caller.yml",
        ".github/workflows/semgrep.yml",
        ".github/workflows/osv-scanner.yml",
    ],
)
def test_required_workflows_have_merge_group_trigger(workflow: str):
    assert "merge_group:" in _repo_text(workflow)


def test_osv_required_workflow_is_not_path_filtered():
    workflow = _repo_text(".github/workflows/osv-scanner.yml")

    assert "\n    paths:" not in workflow
    assert "\n      - 'uv.lock'" not in workflow


def test_tier1_security_scan_runs_secret_guard_and_summarizes_it():
    workflow = _repo_text(".github/workflows/security-scan-caller.yml")

    assert "secret-guard" in workflow
    assert "python scripts/secret_guard.py --all-files" in workflow
    assert "persist-credentials: false" in workflow
    assert "SECRET_GUARD" in workflow


def test_workflows_do_not_keep_stale_checkout_pin():
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    workflow_paths = sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])
    stale_checkout_uses = {
        "actions/checkout@v4.2.2",
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
    }

    for workflow_path in workflow_paths:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                assert step.get("uses") not in stale_checkout_uses


def test_dependabot_groups_github_action_updates():
    config = yaml.safe_load(_repo_text(".github/dependabot.yml"))
    github_actions_updates = [
        update
        for update in config["updates"]
        if update.get("package-ecosystem") == "github-actions"
    ]

    assert len(github_actions_updates) == 1
    assert (
        github_actions_updates[0]
        .get("groups", {})
        .get("github-actions", {})
        .get("patterns")
        == ["*"]
    )


def test_pre_push_hook_uses_target_remote_for_new_branch_base():
    hook = _repo_text(".githooks/pre-push")

    assert "remote_name=" in hook
    assert "origin/main" not in hook
