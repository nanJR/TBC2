-- TBC² database (Supabase project "TBC2", region ap-south-1 Mumbai).
--
-- Security model:
-- * Only the FastAPI back end touches patient data, using the secret (service role) key,
--   which bypasses row-level security. It checks every user's login and role itself.
-- * Row-level security is ON and FORCED on every table, and browser roles (anon,
--   authenticated) get no grants on patient tables, so a leaked publishable key or a
--   signed-in user's token can't read or change any record directly.
-- * The only table a browser may read is profiles, and only the user's own row.
-- * No real patient data: synthetic records only (see CLAUDE.md). ABHA numbers are
--   stored only as keyed hashes.
--
-- Records are stored whole as JSON (the API's Pydantic models are the one definition
-- of each shape), with district and status copied into columns for filtering.

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null check (role in ('practitioner', 'asha', 'coordinator')),
  full_name text not null,
  district text not null,
  place text,
  created_at timestamptz not null default now()
);

create table public.screenings (
  id text primary key,
  district text not null,
  status text not null,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table public.cases (like public.screenings including all);
create table public.patients (like public.screenings including all);
create table public.actions (like public.screenings including all);
create table public.van_slots (like public.screenings including all);

create table public.abha_records (
  abha_hash text primary key check (length(abha_hash) = 64),
  data jsonb not null
);

create table public.audit_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  actor uuid,
  actor_role text,
  action text not null,
  table_name text not null,
  row_id text
);

create index cases_district_status on public.cases (district, status);
create index patients_district on public.patients (district);
create index screenings_district on public.screenings (district);
create index audit_log_at on public.audit_log (at desc);

-- Row-level security everywhere, forced even for table owners.
do $$
declare t text;
begin
  foreach t in array array['profiles', 'screenings', 'cases', 'patients', 'actions',
                           'van_slots', 'abha_records', 'audit_log'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
  end loop;
end $$;

-- A signed-in user may read their own profile (to know their role), nothing else.
grant select on public.profiles to authenticated;
create policy "Users read their own profile"
  on public.profiles for select to authenticated
  using ((select auth.uid()) = id);
