-- Sprint 3: application tables for PlacePrep AI's own auth + resume storage.
-- Run once in the Supabase SQL Editor.
-- The FastAPI backend accesses these via PostgREST using the service_role
-- key (server-side only), so no public RLS policies are defined here.
create table if not exists public.app_users (
  email text primary key,
  name text not null,
  role text not null default 'student',
  hashed_password text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.app_resumes (
  email text primary key,
  filename text,
  resume_text text,
  word_count int,
  skills jsonb not null default '[]'::jsonb,
  uploaded_at timestamptz not null default now()
);

create table if not exists public.app_ats (
  email text primary key,
  result jsonb not null,
  analyzed_at timestamptz not null default now()
);
