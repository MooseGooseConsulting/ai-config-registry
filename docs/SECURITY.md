# Security Model

This document explains what the registry stores, what it does **not** store, and how Supabase and Doppler fit together.

## Your concern is valid: Supabase defaults are dangerous

Supabase exposes tables in the `public` schema through PostgREST. **New tables without Row Level Security (RLS) can be readable with the project's `anon` key** depending on grants.

This project originally shipped only `sql/001_registry_schema.sql` with **no RLS**. That was a real gap — the implementation plan fixed upsert logic but **did not** harden the database until this pass.

**Mitigation (required before any upsert):**

1. Apply `sql/002_row_level_security.sql` via `bootstrap_supabase.ps1`
2. Run `scripts/verify_supabase_security.ps1` — must pass before `-UpsertSupabase`
3. Never put `SUPABASE_SERVICE_KEY` or `anon` keys in the repo, dashboard HTML, or git

## What gets uploaded to Supabase

| Data | Uploaded? | Risk |
|------|-----------|------|
| Secret **values** (API keys, tokens) | **Never** | Scanner redacts MCP command/url fields; upsert strips raw config |
| Secret **names** (`MORPH_API_KEY`, etc.) | Yes, in `secrets_manifest` | Low alone; helps attackers map your key surface |
| File **paths** where keys appear | **Off by default** | High — reveals machine layout; opt-in only |
| Skill paths, hook paths | Yes | Medium — personal machine fingerprint |
| MCP commands/URLs | Redacted copy only | Low if redaction holds |
| `has_plaintext_secret` flags | Yes | Informational — flags misconfigured local files |

Upsert uses `sanitize_for_remote()` in `registry_scanner.py`:

- `secrets_manifest.locations` is **stripped** unless you pass `--include-secret-locations`
- MCP `command_or_url` is already redacted at scan time

## Doppler: is it safe?

**Yes, for the intended pattern:**

- Doppler holds **secret values** (`SUPABASE_SERVICE_KEY`, API keys)
- Supabase holds **inventory metadata** only
- `sync-registry.ps1 -UpsertSupabase` loads credentials via `doppler run` — values never touch disk or git

**Do not:**

- Store Doppler **values** in Supabase (this project doesn't)
- Commit `working/doppler-migration-manifest.json` paths with real usernames to a **public** repo (consider making the GitHub repo private)
- Run `doppler-push-secrets.ps1` in CI logs

**Partial Doppler state (2/12 keys)** does not break security — it means upsert may skip for missing `SUPABASE_SERVICE_KEY`. It does mean other tools won't get secrets from Doppler until you push them.

## Key types — do not confuse them

| Key | Where | Use |
|-----|-------|-----|
| `SUPABASE_SERVICE_KEY` | Doppler only | Server-side upsert; bypasses RLS |
| `anon` key | Supabase dashboard | Browser/client; **must not** access registry tables after RLS migration |
| Doppler service token | Doppler CLI login | Local machine only |

## Local artifacts (gitignored)

`working/registry_snapshot.json` and `registry-dashboard.html` stay on disk only. They can contain paths and redacted MCP config. **Do not commit them.**

## Recommended workflow

```powershell
# 1. Bootstrap schema + RLS (after unpausing Supabase project)
.\scripts\bootstrap_supabase.ps1

# 2. Verify RLS and deny anon access
.\scripts\verify_supabase_security.ps1

# 3. Local scan only (safest default)
.\scripts\sync-registry.ps1 -Verbose

# 4. Remote sync only when RLS verified
.\scripts\sync-registry.ps1 -UpsertSupabase -Verbose
```

## What the original plan missed

The revival plan addressed:

- Broken dashboard, missing `-UpsertSupabase`, upsert `on_conflict`, git backup

It did **not** address:

- RLS / anon exposure (this pass)
- Default upload of secret file paths (now opt-in)
- Public GitHub repo visibility (recommend private)
- Branch protection on `main` (configured separately)
- Post-fix security verification doc (this file)

## GitHub

- `main` branch protection requires pull requests (no direct pushes)
- Prefer **private** repo for a personal machine inventory tool
