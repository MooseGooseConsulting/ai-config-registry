# Forensic Audit — ai-config-registry

**Status:** Pre-fix baseline retained for historical comparison. Concrete workstation paths have been generalized for public safety.

**Audit date:** 2026-06-08  
**Auditor mode:** read-only scan; no Supabase writes, no Doppler push, no secret values printed.

---

## 1. CAPABILITY VERDICT TABLE

| Capability | Claimed status | Evidence found | Verdict |
|------------|----------------|----------------|---------|
| Local config scan (skills, hooks, ecosystems) | README L27–28: `uv run python scripts/registry_scanner.py` | `registry_scan_lib.py` discovers SKILL.md across 13 ecosystem paths; fresh run produced 390 skills, 4 hooks, 13 ecosystems | **WAS-RUN-AND-CORRECT** (pre-fix scan worked; WSL profile paths used a concrete local username) |
| MCP server discovery | README L32–36: MCP configs enumerated | `parse_mcp_configs()` reads 6 config files; snapshot lists 14 unique server names; rows are name-only stubs (`command_or_url: ""`) | **RUNS** (names only; enrichment not implemented) |
| Extra surfaces (AppData, shell, runtime inventory) | README L32–36 | `enumerate_extra_surfaces()` in lib; summary shows 2/2 appdata, 2/6 shell, 4/5 transcript paths | **WAS-RUN-AND-CORRECT** (`.codex/logs` misclassified as file when missing) |
| CLI tool inventory | README L35 | `check_cli_tools()` runs 24 tools; summary shows available/missing per tool | **WAS-RUN-AND-CORRECT** |
| Secrets manifest (metadata only) | README L118; manifest JSON | `build_secrets_manifest_metadata()` scans MCP files for key names; `doppler-migration-manifest.json` has 12 keys + source paths, no values | **EXISTS** (metadata only; never auto-pushed) |
| Dashboard HTML generation | README L99–102 | `generate_registry_dashboard.py` exists; field names mismatch scanner (`slug` vs `name`, `hook_name` vs `path`) | **BROKEN** (renders mostly empty tables) |
| `sync-registry.ps1` orchestration | README L47–59 | Script runs scanner + dashboard; **no `-UpsertSupabase` param** despite README L58–59 | **BROKEN** (missing documented switch) |
| Supabase schema | phase-status L11–17; `sql/001_registry_schema.sql` | 6 tables defined with unique constraints | **EXISTS** (schema file present; bootstrap never executed) |
| Supabase upsert | README L28, L108–109 | `maybe_supabase_upsert()` POSTs local `id` values; no `on_conflict` headers; no ecosystem ID remapping | **BROKEN** (would fail or corrupt FKs on live DB) |
| Supabase bootstrap | `bootstrap_supabase.ps1` | Prints instructions only; does not run `supabase db query --file` | **NEVER-RAN** |
| Doppler check script | README L121 | `check-doppler-state.ps1` with 12 hardcoded keys | **EXISTS** (not run in this audit) |
| Doppler push script | README L119–120 | `doppler-push-secrets.ps1` has duplicate hardcoded key list; manifest not wired | **EXISTS** (orphaned from manifest) |
| Scheduled task registration | README L65–76 | `register-registry-task.ps1` complete, disabled-by-default | **EXISTS** (not registered) |
| Cursor hook integration | README L80–90 | `apply-cursor-hook.ps1` idempotent hook writer | **EXISTS** (not verified run) |
| Git / backup | Plan notes | No `.git`, no `.gitignore`, no `pyproject.toml` | **NEVER-RAN** |
| Drift detection | phase-status "future" | No code references | **NEVER-RAN** |

---

## 2. CLAIM-VS-REALITY GAPS

| Source | Claim | Reality |
|--------|-------|---------|
| `README.md` L58–59 | `-UpsertSupabase` switch on `sync-registry.ps1` | `sync-registry.ps1` has no such parameter (lines 1–7 params only) |
| `README.md` L23 | MCP config updated in `%USERPROFILE%\.cursor\mcp.json` | Out-of-repo change; not verifiable from repo artifacts |
| `working/phase-status.md` L21 | Optional bootstrap "not done" (`[ ]`) | Consistent — bootstrap is instructions-only |
| `working/phase-status.md` L19–20 | Doppler `SUPABASE_SERVICE_KEY` confirmed | Cannot verify from repo; Doppler scripts exist |
| `scripts/bootstrap_supabase.ps1` L24 | "Applying schema with db push path" | Only prints commands; `exit 0` without executing (L31) |
| `scripts/registry_scanner.py` L80–89 | MCP rows populated | Stubs: empty `command_or_url`, `ecosystem_ids: []`, `has_plaintext_secret: false` |
| `scripts/generate_registry_dashboard.py` L179–186 | Skills table uses `slug`, `source_path` | Scanner provides `name`, `path`, `ecosystem_ids` — columns render empty |
| `scripts/generate_registry_dashboard.py` L192–197 | Hooks use `hook_name`, `event_name`, `command` | Scanner provides `path`, `event_type`, `action` |
| `scripts/doppler-push-secrets.ps1` L30–43 | Keys from manifest | Hardcoded duplicate list; manifest at `working/doppler-migration-manifest.json` unused |

---

## 3. RUN RESULT

**Executed today (2026-06-08):** `python scripts/registry_scanner.py` (local only, no `--upsert-supabase`)

| Metric | Prior artifact (2026-04-28) | Fresh run (2026-06-08) |
|--------|----------------------------|------------------------|
| Skills | ~390+ (4557-line snapshot) | 390 |
| MCP servers | 16 names | 14 names |
| Hooks | present | 4 |
| Ecosystems | 13 | 13 |
| Exit code | — | 0 |

**Verdict:** **clean** — scanner executes successfully and produces real machine-specific data (paths under the local Windows profile, real skill names like "Chat History Extractor"). Prior artifact was a genuine prior run, not a stub.

---

## 4. IDEAS VERDICT

**Architecture:** Local-first scanner → JSON snapshot → HTML dashboard → optional Supabase upsert, with Doppler for secrets. Windows-centric paths, manual-first orchestration.

**coldaine-infra-fresh cross-check:**

- `docs/NORTH_STAR.md`: Fleet-wide **database-driven control plane** (Dolt) with drift detection and agent reconciliation — a broader, multi-machine vision.
- `BACKLOG-DISTILLED.md`: Lessons on secrets (per-command scoping), bootstrap paradox, DB-as-control-plane — does **not** include a local AI config scanner.

**Overlap:** coldaine-infra targets fleet desired-state + drift; ai-config-registry targets **local AI tooling inventory** (skills, MCP, hooks, CLI). Different scope — scanner is **not superseded**.

**Worth salvaging:**

1. **`registry_scan_lib.py` + `registry_scanner.py`** — core asset; produces real output.
2. **`generate_registry_dashboard.py`** — fixable schema mismatch.
3. **`sync-registry.ps1` + Doppler scripts** — orchestration layer worth completing.
4. **Supabase schema + upsert** — useful personal registry DB if upsert fixed.
5. **Manifest-driven Doppler workflow** — aligns with coldaine secret-scoping lessons.

**Not worth keeping as-is:** hardcoded paths, stub MCP rows, non-executable bootstrap, missing git backup.

**Salvage decision:** **Proceed with full-stack revival** (user chose this earlier; audit confirms scanner + orchestration are coherent and not superseded).

---

## 5. ONE-LINE BOTTOM LINE

**Partly yes** — the scanner genuinely ran and produced real local inventory (390 skills, 14 MCP names, 13 ecosystems); dashboard, Supabase upsert, sync switch, and git backup are broken or never implemented, but the core idea and scan logic are worth keeping and finishing.

---

## 6. POST-FIX VERIFICATION RECORD

**Verification date:** 2026-06-08
**Scope:** registry truth and secret-guard hardening PR.

| Area | Result | Evidence |
|------|--------|----------|
| Pytest | **pass** | `uv run --extra dev pytest -q` -> 26 passed |
| Repo secret guard | **pass** | `python scripts/secret_guard.py --all-files` -> Secret guard passed |
| Local sync | **pass** | `.\scripts\sync-registry.ps1 -Verbose` -> scanner/dashboard complete; Supabase mode disabled |
| Doppler names check | **partial** | `.\scripts\check-doppler-state.ps1` -> authenticated; `SUPABASE_SERVICE_KEY` present; 10 verification keys missing |
| Supabase strict verifier | **blocked** | `.\scripts\verify_supabase_security.ps1` -> RLS queries failed; bootstrap/RLS not live-verified |
| Supabase upsert | **blocked fail-closed** | `.\scripts\sync-registry.ps1 -UpsertSupabase -Verbose` -> verifier failed before upsert |
| Doppler push dry-run | **pass** | `.\scripts\doppler-push-secrets.ps1 -DryRun` -> 12 manifest keys parsed; no values requested or printed |

**Full-stack complete remains false** until Supabase is active, bootstrap/RLS/anon-denial verification passes, Doppler has the needed keys for the target workflow, and one `-UpsertSupabase` run exits 0.
