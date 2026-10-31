-- PlacePrep AI - Supabase / PostgreSQL Schema (run in Supabase SQL Editor in Sprint 2)
create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text unique not null,
  role text default 'student' check (role in ('student','tpo','admin')),
  college text, branch text, graduation_year int,
  created_at timestamptz default now()
);

create table if not exists resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  file_url text, extracted_text text,
  ats_score int, skills jsonb default '[]',
  created_at timestamptz default now()
);

create table if not exists interviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  role_target text, company text,
  overall_score float, feedback text,
  status text default 'completed',
  created_at timestamptz default now()
);

create table if not exists interview_qa (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id) on delete cascade,
  question text, user_answer text, ideal_answer text,
  score float, feedback text,
  created_at timestamptz default now()
);
