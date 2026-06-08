create table if not exists public.ecosystems (
  id bigserial primary key,
  name text not null unique,
  config_path text,
  type text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.skills (
  id bigserial primary key,
  name text not null,
  path text not null unique,
  description text,
  tags text[] not null default '{}',
  source_of_truth boolean not null default false,
  ecosystem_ids bigint[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.mcp_servers (
  id bigserial primary key,
  name text not null,
  command_or_url text,
  ecosystem_ids bigint[] not null default '{}',
  has_plaintext_secret boolean not null default false,
  doppler_key text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (name, command_or_url)
);

create table if not exists public.hooks (
  id bigserial primary key,
  ecosystem_id bigint references public.ecosystems(id) on delete set null,
  event_type text not null,
  path text,
  action text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ecosystem_id, path)
);

create table if not exists public.secrets_manifest (
  id bigserial primary key,
  secret_name text not null unique,
  doppler_project text not null default 'codingagents',
  doppler_config text not null default 'dev',
  locations text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.cli_tools (
  id bigserial primary key,
  name text not null unique,
  installed boolean not null default false,
  version text,
  path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

