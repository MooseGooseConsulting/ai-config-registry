# Phase Status

## Objective

Bring ai-config-registry to a verified, backed-up running state: local scan, dashboard, Supabase upsert, Doppler validation, git remote, and secret-safe public metadata.

## Status Matrix (2026-06-08)

| Capability | Implemented | Locally verified | Live verified | Blocked | Evidence |
|------------|-------------|------------------|---------------|---------|----------|
| Repository scaffold, README, runbook, tests | yes | yes | n/a | no | `uv run --extra dev pytest -q` -> 26 passed |
| Local scanner and dashboard sync | yes | yes | n/a | no | `.\scripts\sync-registry.ps1 -Verbose` -> scanner/dashboard complete, Supabase disabled |
| Manifest v2 public-safe metadata | yes | yes | n/a | no | `working/doppler-migration-manifest.json` uses `source_refs` and `source_catalog`; no concrete profile paths |
| Doppler push workflow | yes | yes | partial | partial | `.\scripts\doppler-push-secrets.ps1 -DryRun` parsed 12 keys; live mutation not run |
| Doppler state check | yes | yes | partial | partial | `.\scripts\check-doppler-state.ps1` authenticated; required `SUPABASE_SERVICE_KEY` present; 10 verification keys missing |
| Repo secret guard | yes | yes | n/a | no | `python scripts/secret_guard.py --all-files` -> Secret guard passed |
| Git hooks installer | yes | yes | local only | no | `.\scripts\install-git-hooks.ps1` set `core.hooksPath=.githooks` |
| CI required-check materialization | yes | not locally executable | pending PR | pending | Required workflows now include `merge_group`; OSV no longer path-filtered |
| Supabase RLS SQL | yes | static only | no | yes | `sql/002_row_level_security.sql` idempotent; live verifier blocked |
| Supabase strict verifier | yes | yes | no | yes | `.\scripts\verify_supabase_security.ps1` failed RLS queries while live project state is not verified |
| Supabase upsert | yes | fail-closed verified | no | yes | `.\scripts\sync-registry.ps1 -UpsertSupabase -Verbose` refused upsert before scanner write path |

## Current Verification Results

- Local tests: **pass** (`26 passed`).
- Local sync: **pass**; generated artifacts remain gitignored.
- Secret guard: **pass** on tracked files.
- Doppler: **partial**; `SUPABASE_SERVICE_KEY` is present, 10 verification keys are missing.
- Supabase: **blocked**; strict verifier cannot prove RLS/grants/anon denial yet.
- Full-stack complete: **false** until Supabase is active, bootstrap/RLS/anon verification passes, Doppler is complete enough for the target workflow, and one `-UpsertSupabase` run exits 0.

## Notes

- Keep service secrets out of repository files and reports.
- Generated snapshots (`registry_snapshot.json`, `registry-dashboard.html`, `registry_summary.md`) are gitignored.
- Drift detection remains out of scope for this pass.
