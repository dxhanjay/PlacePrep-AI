# PlacePrep AI
**Real-Time AI Mock Interview & Resume Analyzer Platform**

![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat&logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/DB-Supabase%20%2F%20PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![Status](https://img.shields.io/badge/Status-Sprint%201%20complete-yellow?style=flat)

BTech CSE Final-Year Major Project — GD Goenka University, Gurugram.
A placement-preparation platform for final-year students: resume ATS analysis against a job description, real-time AI mock interviews with feedback, and a student readiness dashboard.

> **Current status (honest):** Sprint 1 is complete (auth + dashboard + schema). Resume upload with ATS scoring and the AI mock-interview modules are **in progress** (Sprint 2+), not yet built.

## 🌐 Live Demo
- **App:** https://placeprep-ai-cyan.vercel.app — use Sign Up to create an account and try the dashboard
- **API:** https://placeprep-ai-backend.vercel.app · interactive docs at [/docs](https://placeprep-ai-backend.vercel.app/docs)
- Deployed on Vercel (frontend: Next.js project; backend: FastAPI as a serverless function via `backend/api/index.py`). Sprint 1 stores users in memory, so accounts reset when the backend restarts — the Sprint 2 database removes this limit.

## What is DONE in Sprint 1
- [x] Landing page
- [x] Signup / Login UI + API (JWT Auth, password hashing)
- [x] Protected Dashboard UI (ATS, Interviews, Readiness cards)
- [x] FastAPI backend with Swagger docs
- [x] Supabase DB schema ready for Sprint 2 (`database/schema.sql`)

## Tech Stack
Frontend: Next.js 14 + Tailwind | Backend: FastAPI (Python) | DB: Supabase (Postgres) | AI (later sprints): Gemini API

## How To Run (10 minutes)

### 1. Backend
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate   |  Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```
Open: http://localhost:8000/docs - test /auth/signup there

### 2. Frontend (new terminal)
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```
Open: http://localhost:3000

### 3. Test Flow
Signup -> you go to Dashboard -> Logout -> Login again. That's Sprint 1 demo for your guide.

## Folder Structure
```
placeprep-ai/
  frontend/src/app/  -> page.js (landing), login/, signup/, dashboard/
  frontend/src/components/ lib/
  backend/main.py    -> all Sprint 1 APIs
  database/schema.sql
```

## Roadmap
- [x] **Sprint 1** — Landing, signup/login (JWT + bcrypt), protected dashboard, Supabase schema
- [ ] **Sprint 2** — Resume upload (PDF) + text extraction + ATS score vs job description
- [ ] **Sprint 3** — AI mock interview (voice-based) with scoring and feedback
- [ ] **Sprint 4** — Readiness dashboard analytics, TPO/admin view, deployment

## Deployment (Final Sprint)
Frontend -> Vercel | Backend -> Render | DB -> Supabase (all free)

## Author
**Dhananjoy Mahato** — Final-year BTech CSE, GD Goenka University, Gurugram
LinkedIn: https://www.linkedin.com/in/dhananjoy-mahato-303462272 · GitHub: https://github.com/dxhanjay
