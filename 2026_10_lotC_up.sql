-- Lot C — personal scenarios, client folders, broker profile, anonymous product events.
-- NOT applied by the application. Run it yourself in the Supabase SQL editor, first on a TEST project.
-- Additive only: no existing table (users, ...) is altered, no data is modified.
begin;

create table if not exists public.folders (
  id          uuid primary key,
  owner_email text not null,
  name        text not null check (char_length(name) between 1 and 80),
  created_at  timestamptz not null default now(),
  deleted_at  timestamptz
);
create index if not exists folders_owner_idx on public.folders (owner_email);

create table if not exists public.scenarios (
  id             uuid primary key,
  owner_email    text not null,
  name           text not null check (char_length(name) between 1 and 80),
  folder_id      uuid references public.folders(id) on delete set null,
  aircraft_id    text not null,
  payload        jsonb not null,          -- full assumptions + user-entered field list + results snapshot as saved
  db_version     text not null,
  engine_version text not null,
  config_hash    text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  deleted_at     timestamptz              -- soft delete (recoverable)
);
create index if not exists scenarios_owner_idx on public.scenarios (owner_email, deleted_at);

create table if not exists public.broker_profiles (
  owner_email text primary key,
  broker_name text,
  logo_b64    text,                       -- PNG / JPEG, validated and size-limited by the application
  updated_at  timestamptz not null default now()
);

create table if not exists public.events (
  id         uuid primary key,
  session_id text not null,               -- hashed random per-session id: never an e-mail or a user id
  event      text not null,
  props      jsonb not null default '{}'::jsonb,   -- whitelisted keys only: plan, journey, source
  created_at timestamptz not null default now()
);
create index if not exists events_event_idx on public.events (event, created_at);

-- Owner isolation: RLS on, NO policy for anon / authenticated => only the server-side service key can read or write.
alter table public.folders         enable row level security;
alter table public.scenarios       enable row level security;
alter table public.broker_profiles enable row level security;
alter table public.events          enable row level security;

commit;
