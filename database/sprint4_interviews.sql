-- Sprint 4: mock interview sessions.
-- Run once in the Supabase SQL Editor (after sprint3_app_tables.sql).
-- The full session state (questions snapshot, answers, scores, summary)
-- lives in the state jsonb so the API stays stateless between requests.
create table if not exists public.app_interviews (
  id text primary key,
  email text not null,
  track text not null,
  state jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
