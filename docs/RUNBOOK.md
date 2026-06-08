# AI Config Registry Runbook

Ordered verification checklist for local-first registry sync with optional Supabase and Doppler.

## Prerequisites

- Python 3.11+ (or `uv`)
- Doppler CLI authenticated (`doppler login`)
- Optional: Supabase CLI linked to project `agookcvqnalxxcnhttmd`

## 1. Local scan only

```powershell
cd D:\_projects\ai-config-registry
doppler run --project codingagents --config dev -- python scripts/registry_scanner.py
```

Confirm `working/registry_snapshot.json` and `working/registry_summary.md` are updated.

## 2. Dashboard generation

```powershell
python scripts/generate_registry_dashboard.py
```

Open `working/registry-dashboard.html` and confirm populated Skills, MCP, Hooks, and CLI tables.

## 3. Supabase bootstrap (first time)

```powershell
.\scripts\bootstrap_supabase.ps1
.\scripts\verify_supabase.ps1
```

If the project ref changed, update `ProjectRef` in `bootstrap_supabase.ps1` and Doppler `SUPABASE_URL`.

## 4. Full sync with upsert

```powershell
.\scripts\sync-registry.ps1 -UpsertSupabase -Verbose
```

Expect exit code 0 and per-table upsert status lines.

## 5. Doppler key validation

```powershell
.\scripts\check-doppler-state.ps1
```

All 12 manifest keys should show `[OK]`.

## 6. Automated tests

```powershell
uv run --extra dev pytest
# or: pip install pytest && pytest
```

## 7. Optional automation (disabled by default)

```powershell
.\scripts\register-registry-task.ps1
.\scripts\apply-cursor-hook.ps1
```

## Troubleshooting

| Symptom | Action |
|---------|--------|
| Upsert `failed:http_error:409` on hooks | Run `ALTER TABLE hooks ADD CONSTRAINT ... UNIQUE (ecosystem_id, path)` or re-run bootstrap SQL |
| `missing_env` on upsert | Ensure Doppler has `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` |
| Empty dashboard tables | Re-run scanner first; dashboard reads scanner field names |
| Supabase project paused | Resume in Supabase dashboard or create new project and update refs |
