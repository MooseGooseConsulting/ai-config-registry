-- Lock down registry tables: no anon/authenticated API access.
-- Upserts use SUPABASE_SERVICE_KEY (service_role), which bypasses RLS.
-- This migration is idempotent so bootstrap can be re-run safely.

alter table if exists public.ecosystems enable row level security;
alter table if exists public.skills enable row level security;
alter table if exists public.mcp_servers enable row level security;
alter table if exists public.hooks enable row level security;
alter table if exists public.secrets_manifest enable row level security;
alter table if exists public.cli_tools enable row level security;

revoke all on table public.ecosystems from anon, authenticated;
revoke all on table public.skills from anon, authenticated;
revoke all on table public.mcp_servers from anon, authenticated;
revoke all on table public.hooks from anon, authenticated;
revoke all on table public.secrets_manifest from anon, authenticated;
revoke all on table public.cli_tools from anon, authenticated;

drop policy if exists registry_deny_anon_ecosystems on public.ecosystems;
drop policy if exists registry_deny_auth_ecosystems on public.ecosystems;
drop policy if exists registry_deny_anon_skills on public.skills;
drop policy if exists registry_deny_auth_skills on public.skills;
drop policy if exists registry_deny_anon_mcp_servers on public.mcp_servers;
drop policy if exists registry_deny_auth_mcp_servers on public.mcp_servers;
drop policy if exists registry_deny_anon_hooks on public.hooks;
drop policy if exists registry_deny_auth_hooks on public.hooks;
drop policy if exists registry_deny_anon_secrets_manifest on public.secrets_manifest;
drop policy if exists registry_deny_auth_secrets_manifest on public.secrets_manifest;
drop policy if exists registry_deny_anon_cli_tools on public.cli_tools;
drop policy if exists registry_deny_auth_cli_tools on public.cli_tools;

-- Explicit deny policies (belt-and-suspenders if grants are re-added later).
create policy registry_deny_anon_ecosystems
  on public.ecosystems for all to anon using (false) with check (false);
create policy registry_deny_auth_ecosystems
  on public.ecosystems for all to authenticated using (false) with check (false);

create policy registry_deny_anon_skills
  on public.skills for all to anon using (false) with check (false);
create policy registry_deny_auth_skills
  on public.skills for all to authenticated using (false) with check (false);

create policy registry_deny_anon_mcp_servers
  on public.mcp_servers for all to anon using (false) with check (false);
create policy registry_deny_auth_mcp_servers
  on public.mcp_servers for all to authenticated using (false) with check (false);

create policy registry_deny_anon_hooks
  on public.hooks for all to anon using (false) with check (false);
create policy registry_deny_auth_hooks
  on public.hooks for all to authenticated using (false) with check (false);

create policy registry_deny_anon_secrets_manifest
  on public.secrets_manifest for all to anon using (false) with check (false);
create policy registry_deny_auth_secrets_manifest
  on public.secrets_manifest for all to authenticated using (false) with check (false);

create policy registry_deny_anon_cli_tools
  on public.cli_tools for all to anon using (false) with check (false);
create policy registry_deny_auth_cli_tools
  on public.cli_tools for all to authenticated using (false) with check (false);
