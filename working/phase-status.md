# Phase Status

## Objective

Bring ai-config-registry to a verified, backed-up running state: local scan, dashboard, Supabase upsert, Doppler validation, git remote.

## Complete Criteria

- [x] Repository scaffold exists (`scripts/`, `working/`, `sql/`, `tests/`, `docs/`).
- [x] README defines project purpose, setup, and RUNBOOK link.
- [x] Baseline SQL schema exists for all 6 registry tables (hooks unique constraint added).
- [x] `scripts/bootstrap_supabase.ps1` executes `supabase db query --file` when CLI present.
- [x] `scripts/verify_supabase.ps1` queries table row counts.
- [x] `scripts/sync-registry.ps1` supports `-UpsertSupabase` with per-table status output.
- [x] Scanner uses portable `Path.home()` / `USERPROFILE` paths.
- [x] Dashboard aligned to scanner field names; renders ecosystems, MCP sources, extra surfaces.
- [x] MCP rows enriched with command/url, ecosystem sources, plaintext-secret flag.
- [x] Supabase upsert uses `on_conflict` headers and two-phase ecosystem ID mapping.
- [x] `doppler-push-secrets.ps1` reads `working/doppler-migration-manifest.json`.
- [x] Forensic audit captured in `working/FORENSIC_AUDIT.md`.
- [x] Pytest suite in `tests/`; runbook in `docs/RUNBOOK.md`.
- [x] `.gitignore`, `pyproject.toml`, `.env.example` added.
- [ ] Optional: run bootstrap script against target Supabase project and verify tables (run manually when CLI linked).
- [ ] Optional: scheduled task / Cursor hook registration (manual-first, disabled by default).

## Salvage Decision (2026-06-08)

**Proceed with full-stack revival.** Forensic audit confirmed scanner produces real output; dashboard/upsert/git were broken but fixable. coldaine-infra-fresh does not supersede local AI config inventory.

## Notes

- Keep service secrets out of repository files and reports.
- Generated snapshots (`registry_snapshot.json`, `registry-dashboard.html`, `registry_summary.md`) are gitignored.
- Drift detection remains out of scope for this pass.
