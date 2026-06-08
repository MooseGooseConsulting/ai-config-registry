# AI Config Registry

This repository stores registry metadata and automation for AI tooling configuration, including skills, MCP servers, hooks, CLI tools, and secret manifests.

## Scope

- Keep registry definitions and bootstrap scripts here.
- Keep SQL schema and migration-style files here.
- Keep planning/status notes in `working/`.

## Boundaries

- Do not place implementation files for this project in `D:\_projects\Polypipeline`.
- Do not commit plaintext service secrets.
- Use environment variables (for example `SUPABASE_SERVICE_KEY`) for runtime authentication.

## Security

**Read [docs/SECURITY.md](docs/SECURITY.md) before enabling Supabase upsert.**

Supabase `public` tables without Row Level Security can be exposed via the `anon` API key. This repo ships `sql/002_row_level_security.sql` to deny anon/authenticated access. Apply it with bootstrap, then verify:

```powershell
.\scripts\bootstrap_supabase.ps1
.\scripts\verify_supabase_security.ps1
```

Secret **values** are never uploaded. Secret file **paths** are stripped from upserts unless you pass `--include-secret-locations` (not recommended).

## Setup

### Prerequisites

- Python 3.11+ (or [uv](https://github.com/astral-sh/uv))
- [Doppler CLI](https://docs.doppler.com/docs/install-cli) authenticated (`doppler login`)
- Optional: [Supabase CLI](https://supabase.com/docs/guides/cli) for schema bootstrap

### First run

```powershell
cd D:\_projects\ai-config-registry

# Local scan + dashboard (no Supabase writes)
.\scripts\sync-registry.ps1 -Verbose

# Full sync with Supabase upsert (loads secrets from Doppler)
.\scripts\sync-registry.ps1 -UpsertSupabase -Verbose
```

Copy `.env.example` to `.env` only if you are not using Doppler for `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`.

### Supabase project

Target project ref: `agookcvqnalxxcnhttmd`

```powershell
.\scripts\bootstrap_supabase.ps1
.\scripts\verify_supabase_security.ps1
.\scripts\verify_supabase.ps1
```

### Doppler

- Migration manifest: `working/doppler-migration-manifest.json`
- Validate keys: `.\scripts\check-doppler-state.ps1`
- Interactive push: `.\scripts\doppler-push-secrets.ps1` (reads manifest; use `-DryRun` to preview)

### Tests

```powershell
uv run --extra dev pytest
```

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for the full verification checklist.

## Phase 2: Scanner

- Local-only scan mode (default): `uv run python scripts/registry_scanner.py`
- Optional Supabase upsert mode: `uv run python scripts/registry_scanner.py --upsert-supabase`
- Artifacts (gitignored, machine-specific):
  - `working/registry_snapshot.json`
  - `working/registry_summary.md`
- Additional surfaces included:
  - AppData settings (`Code - Insiders` and `Cursor`)
  - Shell profiles (`PowerShell`, `.bashrc`, `.zshrc`, WSL profile locations)
  - Runtime inventory (`npm -g`, `pipx`, `uv tool list`, `pip list` / `python -m pip list`)
  - Transcript/cache metadata surfaces (`.cursor/.codex/.claude`, `.doppler/fallback`, `.omc/state`)

## Phase E: Safe Sync Automation (Manual-First)

Phase E adds sync orchestration and optional automation hooks, while keeping manual execution as the default.

### Manual Workflow (Default)

Run the sync directly when you want to refresh registry outputs:

```powershell
.\scripts\sync-registry.ps1
```

The sync script runs scanner first, then dashboard generator, unless explicitly skipped:

- Skip scanner: `.\scripts\sync-registry.ps1 -NoScan`
- Skip dashboard: `.\scripts\sync-registry.ps1 -NoDashboard`
- Use PowerShell verbose output: `.\scripts\sync-registry.ps1 -Verbose`
- Attempt Supabase upsert during sync: `.\scripts\sync-registry.ps1 -UpsertSupabase`

If scanner/dashboard scripts are missing, sync fails with actionable guidance and expected path candidates.

### Optional Automation: Scheduled Task

To register a Windows Scheduled Task, run:

```powershell
.\scripts\register-registry-task.ps1
```

Behavior:
- Task is created but **disabled by default** (manual-first safety).
- Enable later with: `Enable-ScheduledTask -TaskName "AI Config Registry Sync"`
- To register and enable in one step: `.\scripts\register-registry-task.ps1 -EnableAfterRegister`

### Optional Automation: Cursor Hook

To add or update a Cursor `PostAgentTurn` hook that runs registry sync:

```powershell
.\scripts\apply-cursor-hook.ps1
```

Behavior:
- Script is idempotent (safe to run repeatedly).
- Existing hooks are preserved.
- Existing registry-sync hook entries are updated in place when found.
- Default hook command runs sync with `-NoDashboard` to keep turn-time overhead low.

## Tooling Notes

- Preferred path for schema application is Supabase CLI (`bootstrap_supabase.ps1`).
- If Supabase CLI is unavailable, use fallback instructions in `scripts/bootstrap_supabase.ps1` for direct SQL application (`psql` or Supabase SQL Editor).

## Registry Dashboard

- Generate the self-contained dashboard HTML from the snapshot:
  - `python scripts/generate_registry_dashboard.py`
- Input snapshot: `working/registry_snapshot.json`
- Output HTML: `working/registry-dashboard.html`

## Registry Scanner (Phase B)

- Generate local artifacts:
  - `uv run python scripts/registry_scanner.py`
- Generate artifacts and attempt optional Supabase upsert when env vars are set:
  - `doppler run --project codingagents --config dev -- uv run python scripts/registry_scanner.py --upsert-supabase`

Scanner outputs are written to:

- `working/registry_snapshot.json`
- `working/registry_summary.md`

## Doppler Workflow (Phase C)

- Migration manifest: `working/doppler-migration-manifest.json` (keys, target Doppler key names, and source paths; no values).
- Push interactively: `.\scripts\doppler-push-secrets.ps1` (reads manifest; defaults to project `codingagents`, config `dev`).
- Preview without writing: `.\scripts\doppler-push-secrets.ps1 -DryRun`.
- Read-only validation: `.\scripts\check-doppler-state.ps1`.
- These scripts are designed to avoid echoing secret values to console output.
