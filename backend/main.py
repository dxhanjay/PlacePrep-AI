"""
PlacePrep AI - Backend (Sprints 1-5)
FastAPI: Health, Signup, Login (JWT), Me, Dashboard Stats,
         Resume Upload (PDF) + Text Extraction + ATS Scoring vs a Job Description,
         Mock Interviews with instant scoring, Readiness Analytics, TPO Overview
Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
Storage: Supabase Postgres via PostgREST when SUPABASE_URL + SUPABASE_KEY
are set (required on serverless hosts), in-memory fallback for local dev.
App tables: database/sprint3_app_tables.sql
"""
import io
import json
import os
import random
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pypdf import PdfReader
from pydantic import BaseModel, EmailStr

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

app = FastAPI(title="PlacePrep AI API", version="1.0-sprint1")
# Allowed frontend origins: comma-separated env var for deployment,
# defaults to the local Next.js dev server.
_allowed = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ---------------------------------------------------------------------------
# Storage (Sprint 3): Supabase PostgREST when SUPABASE_URL + SUPABASE_KEY are
# configured; otherwise in-memory dicts so local development still runs with
# zero setup. Serverless deployments MUST use Supabase: each function instance
# has its own memory, so in-memory users made uploads fail with
# "User not found" whenever a request landed on a different instance.
# ---------------------------------------------------------------------------
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or ""
DB_ENABLED = bool(SUPABASE_URL and SUPABASE_KEY)

users_db = {}    # fallback only (local dev without Supabase)
resumes_db = {}  # fallback only
ats_db = {}      # fallback only


def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _sb_get_one(table: str, email: str):
    with httpx.Client(timeout=10) as client:
        res = client.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            params={"email": f"eq.{email}", "select": "*"},
        )
        res.raise_for_status()
        rows = res.json()
        return rows[0] if rows else None


def _sb_upsert(table: str, row: dict):
    headers = _sb_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    with httpx.Client(timeout=10) as client:
        res = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, json=row)
        res.raise_for_status()


def _sb_delete(table: str, email: str):
    with httpx.Client(timeout=10) as client:
        res = client.delete(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            params={"email": f"eq.{email}"},
        )
        res.raise_for_status()


def db_get_user(email: str):
    if DB_ENABLED:
        return _sb_get_one("app_users", email)
    return users_db.get(email)


def db_create_user(user: dict):
    if DB_ENABLED:
        _sb_upsert("app_users", user)
    else:
        users_db[user["email"]] = user


def db_get_resume(email: str):
    if DB_ENABLED:
        row = _sb_get_one("app_resumes", email)
        if not row:
            return None
        return {
            "filename": row["filename"],
            "text": row["resume_text"],
            "word_count": row["word_count"],
            "skills": row["skills"] or [],
            "uploaded_at": row["uploaded_at"],
        }
    return resumes_db.get(email)


def db_save_resume(email: str, record: dict):
    if DB_ENABLED:
        _sb_upsert("app_resumes", {
            "email": email,
            "filename": record["filename"],
            "resume_text": record["text"],
            "word_count": record["word_count"],
            "skills": record["skills"],
            "uploaded_at": record["uploaded_at"],
        })
    else:
        resumes_db[email] = record


def db_get_ats(email: str):
    if DB_ENABLED:
        row = _sb_get_one("app_ats", email)
        return row["result"] if row else None
    return ats_db.get(email)


def db_save_ats(email: str, result: dict):
    if DB_ENABLED:
        _sb_upsert("app_ats", {
            "email": email,
            "result": result,
            "analyzed_at": result.get("analyzed_at") or datetime.utcnow().isoformat(),
        })
    else:
        ats_db[email] = result


def db_clear_ats(email: str):
    if DB_ENABLED:
        _sb_delete("app_ats", email)
    else:
        ats_db.pop(email, None)


interviews_db = {}  # fallback only: session id -> interview state


def _sb_list_interviews(email: str):
    with httpx.Client(timeout=10) as client:
        res = client.get(
            f"{SUPABASE_URL}/rest/v1/app_interviews",
            headers=_sb_headers(),
            params={"email": f"eq.{email}", "select": "*", "order": "created_at.desc"},
        )
        res.raise_for_status()
        return res.json()


def db_create_interview(state: dict):
    if DB_ENABLED:
        _sb_upsert("app_interviews", {
            "id": state["id"], "email": state["email"], "track": state["track"],
            "state": state, "created_at": state["created_at"],
            "updated_at": state["updated_at"],
        })
    else:
        interviews_db[state["id"]] = state


def db_get_interview(session_id: str):
    if DB_ENABLED:
        with httpx.Client(timeout=10) as client:
            res = client.get(
                f"{SUPABASE_URL}/rest/v1/app_interviews",
                headers=_sb_headers(),
                params={"id": f"eq.{session_id}", "select": "*"},
            )
            res.raise_for_status()
            rows = res.json()
            return rows[0]["state"] if rows else None
    return interviews_db.get(session_id)


def db_update_interview(state: dict):
    state["updated_at"] = datetime.utcnow().isoformat()
    db_create_interview(state)


def db_list_interviews(email: str):
    if DB_ENABLED:
        return [row["state"] for row in _sb_list_interviews(email)]
    mine = [s for s in interviews_db.values() if s["email"] == email]
    return sorted(mine, key=lambda s: s["created_at"], reverse=True)

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "student"  # student | tpo

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

def create_token(email: str):
    exp = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db_get_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.get("/")
def health():
    return {"status": "ok", "project": "PlacePrep AI", "sprint": 5,
            "storage": "supabase" if DB_ENABLED else "memory"}

@app.post("/auth/signup")
def signup(data: SignupRequest):
    if db_get_user(data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = {
        "name": data.name, "email": data.email, "role": data.role,
        "hashed_password": pwd_context.hash(data.password),
        "created_at": datetime.utcnow().isoformat(),
    }
    db_create_user(user)
    return {"message": "Signup successful", "token": create_token(data.email),
            "user": {"name": user["name"], "email": user["email"], "role": user["role"]}}

@app.post("/auth/login")
def login(data: LoginRequest):
    user = db_get_user(data.email)
    if not user or not pwd_context.verify(data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"message": "Login successful", "token": create_token(data.email),
            "user": {"name": user["name"], "email": user["email"], "role": user["role"]}}

@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {"name": user["name"], "email": user["email"], "role": user["role"]}

@app.get("/dashboard/stats")
def dashboard_stats(user=Depends(get_current_user)):
    email = user["email"]
    last_ats = db_get_ats(email)
    has_resume = db_get_resume(email) is not None
    if last_ats:
        weak = [f"Missing skill: {s}" for s in last_ats["missing_skills"][:3]]
        weak_topics = weak or ["No major skill gaps against your last JD"]
    elif has_resume:
        weak_topics = ["Run an ATS check against a job description"]
    else:
        weak_topics = ["Upload your resume to unlock your ATS score"]
    sessions = db_list_interviews(email)
    completed = [s for s in sessions if s.get("status") == "completed" and s.get("summary")]
    interview_avg = (sum(s["summary"]["overall_score"] for s in completed) / len(completed)) if completed else None
    ats_score = last_ats["score"] if last_ats else 0
    # Readiness blends the two things a student controls: resume strength and
    # interview performance. Each contributes up to 50 points.
    readiness = 0
    if last_ats:
        readiness += round(ats_score * 0.5)
    if interview_avg is not None:
        readiness += round(interview_avg * 0.5)
    return {
        "user": user["name"],
        "ats_score": ats_score,
        "interviews_completed": len(completed),
        "last_interview_score": round(interview_avg) if interview_avg is not None else None,
        "readiness_score": readiness,
        "has_resume": has_resume,
        "weak_topics": weak_topics,
        "recent_activity": []
    }


# ---------------------------------------------------------------------------
# Sprint 2: Resume upload + ATS scoring
# ---------------------------------------------------------------------------
SKILL_KEYWORDS = [
    "python", "sql", "java", "javascript", "typescript", "c++", "c#", "golang",
    "react", "next.js", "node.js", "express", "fastapi", "flask", "django",
    "spring boot", "html", "css", "tailwind", "rest api", "graphql",
    "pandas", "numpy", "matplotlib", "excel", "power bi", "tableau",
    "machine learning", "deep learning", "tensorflow", "pytorch", "opencv",
    "nlp", "scikit-learn", "statistics",
    "etl", "elt", "spark", "airflow", "kafka", "hadoop", "data pipeline",
    "data warehousing", "data modeling", "dbt", "snowflake",
    "postgresql", "mysql", "sqlite", "mongodb", "redis",
    "aws", "azure", "gcp", "docker", "kubernetes", "git", "github",
    "linux", "ci/cd", "agile", "jira",
    "data structures", "algorithms", "oop", "operating systems", "dbms",
    "computer networks", "system design",
]

SECTION_PATTERNS = {
    "education": r"education|university|college|b\.?tech|bachelor|degree",
    "experience": r"experience|internship|intern|work history|employment",
    "projects": r"projects?|portfolio",
    "skills": r"skills?|technical expertise|technologies",
    "summary": r"summary|objective|profile|about me",
}

ACTION_VERBS = [
    "built", "developed", "designed", "implemented", "created", "improved",
    "optimized", "automated", "deployed", "led", "achieved", "reduced",
    "increased", "analyzed", "engineered", "delivered", "maintained",
]

STOPWORDS = set("""the and for with you your are will this that from have has our can all any per
job role work team using use used skills experience years year required requirements including
ability strong knowledge plus etc within across support business data new one two day days""".split())


def find_skills(text: str):
    low = " " + text.lower() + " "
    found = []
    for skill in SKILL_KEYWORDS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, low):
            found.append(skill)
    return sorted(found)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def analyze_resume(resume_text: str, jd_text: str) -> dict:
    resume_skills = set(find_skills(resume_text))
    jd_skills = set(find_skills(jd_text))
    matched = sorted(resume_skills & jd_skills)
    missing = sorted(jd_skills - resume_skills)

    # Keyword score (60 pts): share of JD skills the resume evidences.
    # If the JD names no known skills, fall back to content-word overlap.
    if jd_skills:
        keyword_points = 60.0 * len(matched) / len(jd_skills)
        keyword_basis = f"{len(matched)}/{len(jd_skills)} job skills found in resume"
    else:
        jd_words = [w for w in re.findall(r"[a-z][a-z0-9+#.]{3,}", jd_text.lower())
                    if w not in STOPWORDS]
        top_jd = {w for w, _ in sorted({w: jd_words.count(w) for w in set(jd_words)}.items(),
                                       key=lambda kv: -kv[1])[:30]}
        resume_low = resume_text.lower()
        hits = {w for w in top_jd if w in resume_low}
        keyword_points = 60.0 * (len(hits) / len(top_jd)) if top_jd else 0.0
        keyword_basis = f"{len(hits)}/{len(top_jd)} frequent JD terms found in resume"

    # Section score (25 pts): 5 points per key section present.
    low = resume_text.lower()
    sections_found, sections_missing = [], []
    for name, pattern in SECTION_PATTERNS.items():
        (sections_found if re.search(pattern, low) else sections_missing).append(name)
    section_points = 5.0 * len(sections_found)

    # Length score (10 pts): resumes in the 250-1200 word band are ATS-friendly.
    words = len(resume_text.split())
    if 250 <= words <= 1200:
        length_points = 10.0
    elif 150 <= words < 250 or 1200 < words <= 1600:
        length_points = 6.0
    else:
        length_points = 3.0

    # Action-verb score (5 pts).
    verbs_found = [v for v in ACTION_VERBS if re.search(r"\b" + v + r"\b", low)]
    verb_points = min(5.0, float(len(verbs_found)))

    score = int(round(keyword_points + section_points + length_points + verb_points))

    suggestions = []
    if missing:
        suggestions.append("Add or evidence these job skills: " + ", ".join(missing[:8]))
    for name in sections_missing:
        suggestions.append(f"Add a clear '{name}' section")
    if length_points < 10:
        suggestions.append("Aim for a focused 1-2 page resume (roughly 250-1200 words)")
    if len(verbs_found) < 5:
        suggestions.append("Start more bullet points with action verbs (built, deployed, optimized...)")
    if not suggestions:
        suggestions.append("Strong match — tailor the summary line to this exact role and apply")

    return {
        "score": score,
        "breakdown": {
            "keyword_match": round(keyword_points, 1),
            "sections": round(section_points, 1),
            "length": round(length_points, 1),
            "action_verbs": round(verb_points, 1),
        },
        "keyword_basis": keyword_basis,
        "matched_skills": matched,
        "missing_skills": missing,
        "resume_skills": sorted(resume_skills),
        "sections_found": sections_found,
        "sections_missing": sections_missing,
        "word_count": words,
        "suggestions": suggestions,
    }


class ATSRequest(BaseModel):
    job_description: str


@app.post("/resume/upload")
async def upload_resume(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    try:
        text = extract_pdf_text(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF — is it a valid PDF file?")
    if len(text.split()) < 30:
        raise HTTPException(status_code=400,
                            detail="Almost no text found in this PDF. Scanned/image resumes are not supported yet — please upload a text-based PDF.")
    record = {
        "filename": file.filename,
        "text": text,
        "word_count": len(text.split()),
        "skills": find_skills(text),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    db_save_resume(user["email"], record)
    # Note: the previous ATS result is kept (it records the filename it was
    # computed on) instead of being wiped on every re-upload — students
    # re-upload often while fixing their resume, and a vanished score reads
    # as data loss. Running a new analysis overwrites it.
    return {
        "message": "Resume uploaded and parsed",
        "filename": record["filename"],
        "word_count": record["word_count"],
        "skills_detected": record["skills"],
        "uploaded_at": record["uploaded_at"],
    }


@app.get("/resume/me")
def my_resume(user=Depends(get_current_user)):
    record = db_get_resume(user["email"])
    if not record:
        return {"has_resume": False}
    return {
        "has_resume": True,
        "filename": record["filename"],
        "word_count": record["word_count"],
        "skills_detected": record["skills"],
        "uploaded_at": record["uploaded_at"],
        "last_ats": db_get_ats(user["email"]),
    }


@app.post("/resume/ats")
def ats_check(data: ATSRequest, user=Depends(get_current_user)):
    record = db_get_resume(user["email"])
    if not record:
        raise HTTPException(status_code=400, detail="Upload your resume first")
    if len(data.job_description.strip()) < 50:
        raise HTTPException(status_code=400, detail="Please paste a fuller job description (at least a paragraph)")
    result = analyze_resume(record["text"], data.job_description)
    result["filename"] = record["filename"]
    result["analyzed_at"] = datetime.utcnow().isoformat()
    db_save_ats(user["email"], result)
    return result


# ---------------------------------------------------------------------------
# Sprint 4: AI Mock Interview (question bank + instant rule-based evaluation)
# ---------------------------------------------------------------------------
# Evaluation philosophy: every question carries the key points a strong
# answer should cover. Answers are scored on key-point coverage (70),
# depth/length (20) and structure signals like examples and numbers (10),
# with the matched/missed points returned as feedback. A generative-AI
# evaluator can later be plugged into evaluate_answer() behind the same API.
QUESTIONS_PER_SESSION = 5

INTERVIEW_TRACKS = {
    "data-engineering": {
        "title": "Data Engineering",
        "questions": [
            {"id": "de1", "q": "Explain ETL vs ELT. When would you choose one over the other?",
             "points": [
                 {"label": "ETL: transform before loading into the target", "keys": ["transform before", "before loading", "etl"]},
                 {"label": "ELT: load raw first, transform inside the warehouse", "keys": ["load raw", "raw first", "transform in", "elt"]},
                 {"label": "Choice depends on data volume / warehouse compute / governance", "keys": ["volume", "warehouse", "compute", "governance", "cost", "compliance"]}],
             "tip": "Anchor it in a real pipeline: raw layer first, then clean — that is ELT thinking."},
            {"id": "de2", "q": "What are the different types of SQL JOINs, and when do you use each?",
             "points": [
                 {"label": "INNER JOIN returns only matching rows", "keys": ["inner", "matching"]},
                 {"label": "LEFT JOIN keeps all rows from the left table", "keys": ["left", "all rows from the left", "left table"]},
                 {"label": "FULL OUTER / RIGHT / CROSS awareness", "keys": ["full", "right", "cross"]},
                 {"label": "Unmatched rows become NULL in outer joins", "keys": ["null"]}],
             "tip": "Give a tiny two-table example for one join — examples score well."},
            {"id": "de3", "q": "What is a window function? Give an example where a GROUP BY cannot do the job.",
             "points": [
                 {"label": "Window functions compute across related rows without collapsing them", "keys": ["without collapsing", "does not collapse", "keeps rows", "related rows", "set of rows"]},
                 {"label": "OVER() and PARTITION BY define the window", "keys": ["over", "partition by"]},
                 {"label": "Concrete example: RANK / running total / LAG with row detail preserved", "keys": ["rank", "running total", "lag", "row_number", "top 3 per", "per group"]}],
             "tip": "The classic example: top 3 salaries per department — GROUP BY alone loses the row detail."},
            {"id": "de4", "q": "How do you make a data pipeline idempotent, and why does it matter?",
             "points": [
                 {"label": "Same input produces the same output / safe to re-run", "keys": ["same output", "re-run", "rerun", "safe to run again", "same result"]},
                 {"label": "Upserts / merge on a natural key instead of blind appends", "keys": ["upsert", "merge", "insert or replace", "natural key", "primary key", "deduplicate"]},
                 {"label": "Matters because retries and failures must not duplicate data", "keys": ["duplicat", "retr", "fail"]}],
             "tip": "Mention your own pipeline: INSERT OR REPLACE on the hour timestamp is idempotency in action."},
            {"id": "de5", "q": "Data warehouse vs data lake vs lakehouse — what is the difference?",
             "points": [
                 {"label": "Warehouse: structured, schema-on-write, SQL analytics", "keys": ["structured", "schema-on-write", "schema on write"]},
                 {"label": "Lake: raw files of any type, schema-on-read", "keys": ["raw", "schema-on-read", "schema on read", "object storage", "files"]},
                 {"label": "Lakehouse combines both (e.g. Delta/Iceberg)", "keys": ["lakehouse", "delta", "iceberg", "combine", "both"]}],
             "tip": "One line each is enough — interviewers want the contrast, not an essay."},
            {"id": "de6", "q": "Your pipeline receives duplicate and late-arriving records. How do you handle them?",
             "points": [
                 {"label": "Deduplicate on a business/natural key", "keys": ["dedup", "duplicate", "distinct", "natural key", "unique"]},
                 {"label": "Watermark / event-time handling for late data", "keys": ["watermark", "late", "event time", "window"]},
                 {"label": "Data-quality checks that flag or quarantine bad rows", "keys": ["quality check", "validation", "quarantine", "flag", "reject"]}],
             "tip": "Structure it: detect → decide (drop/merge/quarantine) → make it visible in logs."},
        ],
    },
    "python-sql": {
        "title": "Python + SQL",
        "questions": [
            {"id": "ps1", "q": "List vs tuple in Python — differences and when do you use each?",
             "points": [
                 {"label": "Lists are mutable, tuples are immutable", "keys": ["mutable", "immutable"]},
                 {"label": "Tuples can be dictionary keys / are hashable", "keys": ["hashable", "dictionary key", "dict key"]},
                 {"label": "Use cases: fixed records vs growing collections", "keys": ["fixed", "coordinates", "return multiple", "collection"]}],
             "tip": "Immutability first, hashability second, use case third."},
            {"id": "ps2", "q": "How would you find duplicate values in a SQL table? Write the query approach.",
             "points": [
                 {"label": "GROUP BY the column(s)", "keys": ["group by"]},
                 {"label": "HAVING COUNT(*) > 1 filters the duplicates", "keys": ["having", "count"]},
                 {"label": "Window function alternative (ROW_NUMBER) to fetch full rows", "keys": ["row_number", "window"]}],
             "tip": "GROUP BY + HAVING is the core; ROW_NUMBER shows senior-level polish."},
            {"id": "ps3", "q": "What does an index do in a database, and what is its downside?",
             "points": [
                 {"label": "Speeds up reads/lookups (B-tree search instead of full scan)", "keys": ["speed", "faster", "lookup", "b-tree", "btree", "full scan", "search"]},
                 {"label": "Downside: slower writes and extra storage", "keys": ["slower write", "write", "storage", "space", "overhead"]},
                 {"label": "Best on filtered/joined columns", "keys": ["where", "join", "filter", "frequently"]}],
             "tip": "Every index is a trade: read speed paid for with write cost."},
            {"id": "ps4", "q": "Explain Python generators and why they matter for data work.",
             "points": [
                 {"label": "Yield values lazily, one at a time", "keys": ["yield", "lazy", "one at a time"]},
                 {"label": "Memory efficient for large/streaming data", "keys": ["memory", "large", "stream"]},
                 {"label": "Example: processing a big file line by line", "keys": ["file", "line", "csv", "log"]}],
             "tip": "Connect it to pipelines: stream records instead of loading everything into RAM."},
            {"id": "ps5", "q": "WHERE vs HAVING in SQL — what is the difference?",
             "points": [
                 {"label": "WHERE filters rows before grouping", "keys": ["before group", "before aggregation", "individual rows", "row level"]},
                 {"label": "HAVING filters groups after aggregation", "keys": ["after", "group", "aggregat"]},
                 {"label": "Aggregates like SUM/COUNT belong in HAVING", "keys": ["sum", "count", "avg", "aggregate function"]}],
             "tip": "Timeline answer: WHERE → GROUP BY → HAVING → ORDER BY."},
            {"id": "ps6", "q": "How do you handle missing or null values when cleaning data in pandas?",
             "points": [
                 {"label": "Detect them first (isna / value counts / info)", "keys": ["isna", "isnull", "detect", "info"]},
                 {"label": "Decide per column: drop, fill (mean/median/constant), or flag", "keys": ["dropna", "fillna", "fill", "median", "mean", "impute"]},
                 {"label": "Never silently guess — document the choice", "keys": ["document", "domain", "reason", "business", "depends"]}],
             "tip": "The decision matters more than the function name — say why for each column."},
        ],
    },
    "dsa-basics": {
        "title": "DSA Basics",
        "questions": [
            {"id": "dsa1", "q": "Why is binary search O(log n), and what must be true about the input?",
             "points": [
                 {"label": "The array must be sorted", "keys": ["sorted"]},
                 {"label": "Each step halves the search space", "keys": ["half", "halv", "divide"]},
                 {"label": "log n comes from repeated halving", "keys": ["log", "2^k", "power"]}],
             "tip": "Say the recurrence out loud: T(n) = T(n/2) + O(1)."},
            {"id": "dsa2", "q": "When would you use a hash map to solve a problem? Give an example.",
             "points": [
                 {"label": "O(1) average lookup / membership testing", "keys": ["o(1)", "constant", "lookup", "membership"]},
                 {"label": "Example: Two Sum / frequency counting / caching seen values", "keys": ["two sum", "frequency", "count", "seen", "complement"]},
                 {"label": "Trade-off: extra memory for speed", "keys": ["memory", "space", "trade"]}],
             "tip": "Two Sum is the perfect 20-second example: store complements as you scan."},
            {"id": "dsa3", "q": "Stack vs queue — differences and one real use case each.",
             "points": [
                 {"label": "Stack is LIFO, queue is FIFO", "keys": ["lifo", "fifo", "last in", "first in"]},
                 {"label": "Stack use: undo, recursion, bracket matching", "keys": ["undo", "recursion", "bracket", "backtrack", "call stack"]},
                 {"label": "Queue use: BFS, scheduling, buffers", "keys": ["bfs", "schedul", "buffer", "printer", "task"]}],
             "tip": "Name the operations too: push/pop vs enqueue/dequeue."},
            {"id": "dsa4", "q": "BFS vs DFS — how do they differ and when is each better?",
             "points": [
                 {"label": "BFS explores level by level using a queue", "keys": ["level", "queue"]},
                 {"label": "DFS goes deep first using a stack/recursion", "keys": ["deep", "stack", "recursion"]},
                 {"label": "BFS finds shortest path in unweighted graphs", "keys": ["shortest path", "unweighted", "nearest"]}],
             "tip": "Shortest path → BFS. Exploring all paths / topological order → DFS."},
            {"id": "dsa5", "q": "Array vs linked list — trade-offs for access, insert and delete.",
             "points": [
                 {"label": "Array: O(1) index access, costly middle inserts", "keys": ["o(1) access", "index", "random access", "shift"]},
                 {"label": "Linked list: O(1) insert/delete at a known node, O(n) access", "keys": ["insert", "delete", "o(n) access", "pointer"]},
                 {"label": "Memory/cache behaviour differs", "keys": ["cache", "contiguous", "memory", "pointer overhead"]}],
             "tip": "Make a mini table in words: access, insert, delete, memory."},
            {"id": "dsa6", "q": "Quicksort vs mergesort — compare time, space and stability.",
             "points": [
                 {"label": "Both average O(n log n); quicksort worst case O(n^2)", "keys": ["n log n", "n^2", "worst"]},
                 {"label": "Mergesort needs O(n) extra space; quicksort is in-place", "keys": ["o(n) space", "extra space", "in-place", "in place"]},
                 {"label": "Mergesort is stable, quicksort is not", "keys": ["stable"]}],
             "tip": "Pivot choice is the quicksort caveat interviewers listen for."},
        ],
    },
    "hr-behavioral": {
        "title": "HR / Behavioral",
        "questions": [
            {"id": "hr1", "q": "Tell me about yourself.",
             "points": [
                 {"label": "Present: final-year CSE student and current focus", "keys": ["final year", "final-year", "cse", "student", "currently"]},
                 {"label": "Proof: a concrete project or internship", "keys": ["project", "built", "internship", "placeprep", "etl", "sail"]},
                 {"label": "Direction: the role/field you are targeting and why", "keys": ["data engineering", "looking for", "aim", "goal", "interested in"]}],
             "tip": "Present → proof → direction, in about 60 seconds. No life story."},
            {"id": "hr2", "q": "Describe a challenging project you worked on. What was hard and how did you handle it?",
             "points": [
                 {"label": "Situation: what the project was", "keys": ["project", "building", "built", "develop"]},
                 {"label": "Challenge: a specific hard problem", "keys": ["challenge", "problem", "bug", "difficult", "stuck", "error"]},
                 {"label": "Action + result: what you did and the outcome", "keys": ["fixed", "solved", "learned", "result", "finally", "deployed", "worked"]}],
             "tip": "Use STAR: Situation, Task, Action, Result — with one measurable outcome."},
            {"id": "hr3", "q": "What is your biggest strength, and one weakness you are actively improving?",
             "points": [
                 {"label": "Strength backed by an example", "keys": ["strength", "good at", "example", "because"]},
                 {"label": "A real but non-fatal weakness", "keys": ["weakness", "improv", "struggle", "working on"]},
                 {"label": "Concrete steps being taken to improve", "keys": ["practice", "daily", "plan", "course", "routine"]}],
             "tip": "Weakness + your system to fix it beats a fake weakness every time."},
            {"id": "hr4", "q": "Why do you want to work in data engineering?",
             "points": [
                 {"label": "Genuine interest in data/pipelines", "keys": ["data", "pipeline", "etl", "enjoy", "interest"]},
                 {"label": "Evidence: something you built or learned", "keys": ["built", "project", "learned", "sql", "python"]},
                 {"label": "Fit: how it matches your skills and goals", "keys": ["skill", "goal", "career", "fit", "grow"]}],
             "tip": "Interest + evidence + fit. Your ETL project is your evidence — name it."},
            {"id": "hr5", "q": "Tell me about a time you disagreed with a teammate. How did you resolve it?",
             "points": [
                 {"label": "A specific situation, told neutrally", "keys": ["team", "teammate", "group", "disagree", "different"]},
                 {"label": "You listened and discussed with data/reasons", "keys": ["discuss", "listen", "understood", "reason", "data", "talked"]},
                 {"label": "Resolution and what you learned", "keys": ["decided", "agreed", "learned", "compromise", "result"]}],
             "tip": "Never blame. Process (discuss → decide → commit) is what they score."},
            {"id": "hr6", "q": "Where do you see yourself in 3 years?",
             "points": [
                 {"label": "A clear direction (role/domain)", "keys": ["data engineer", "engineer", "role", "domain"]},
                 {"label": "Skills/depth you want to own by then", "keys": ["expert", "deep", "speciali", "own", "lead"]},
                 {"label": "Growth mindset tied to this opportunity", "keys": ["learn", "grow", "contribute", "company", "team"]}],
             "tip": "Ambitious but anchored: direction + depth + contribution."},
        ],
    },
}


def evaluate_answer(question: dict, answer: str) -> dict:
    text = " " + answer.lower() + " "
    matched, missed = [], []
    for point in question["points"]:
        if any(re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", text) or k in text
               for k in point["keys"]):
            matched.append(point["label"])
        else:
            missed.append(point["label"])
    coverage = len(matched) / len(question["points"]) if question["points"] else 0
    coverage_points = coverage * 70

    words = len(answer.split())
    if 40 <= words <= 180:
        depth_points = 20.0
    elif 20 <= words < 40 or 180 < words <= 260:
        depth_points = 13.0
    elif words >= 8:
        depth_points = 7.0
    else:
        depth_points = 2.0

    structure_signals = 0
    if re.search(r"for example|e\.g\.|such as|in my project|i built|i used", text):
        structure_signals += 1
    if re.search(r"\d", answer):
        structure_signals += 1
    if re.search(r"because|so that|therefore|which means|this helps", text):
        structure_signals += 1
    structure_points = min(10.0, structure_signals * 4.0)

    score = int(round(coverage_points + depth_points + structure_points))
    if score >= 80:
        verdict = "Strong answer"
    elif score >= 55:
        verdict = "Decent answer — a few gaps"
    elif score >= 30:
        verdict = "Partial — key points missing"
    else:
        verdict = "Too thin — needs the core concepts"
    return {
        "score": score, "verdict": verdict,
        "matched_points": matched, "missed_points": missed,
        "word_count": words, "tip": question["tip"],
    }


class StartInterviewRequest(BaseModel):
    track: str


class AnswerRequest(BaseModel):
    session_id: str
    answer: str
    # Sprint 5: "voice" when the answer was dictated with the microphone,
    # "text" when typed. Recorded per answer for analytics.
    input_mode: str = "text"


def public_question(state: dict):
    idx = state["index"]
    if idx >= len(state["questions"]):
        return None
    q = state["questions"][idx]
    return {"number": idx + 1, "total": len(state["questions"]), "question": q["q"]}


def summarize(state: dict) -> dict:
    answers = state["answers"]
    overall = round(sum(a["score"] for a in answers) / len(answers)) if answers else 0
    per_question = [{
        "question": a["question"], "score": a["score"],
        "matched_points": a["matched_points"], "missed_points": a["missed_points"],
    } for a in answers]
    strengths = [a["question"] for a in answers if a["score"] >= 70]
    improvements = []
    for a in sorted(answers, key=lambda x: x["score"])[:2]:
        improvements.extend(a["missed_points"][:2])
    if overall >= 80:
        grade = "Interview-ready for this track"
    elif overall >= 55:
        grade = "Close — polish the gaps below"
    else:
        grade = "Keep practising — focus on the missed points"
    return {
        "overall_score": overall, "grade": grade,
        "per_question": per_question,
        "strengths": strengths, "improvements": improvements,
        "voice_answers": sum(1 for a in answers if a.get("input_mode") == "voice"),
    }


@app.get("/interview/tracks")
def interview_tracks():
    return {"tracks": [
        {"id": tid, "title": t["title"], "questions_available": len(t["questions"]),
         "per_session": QUESTIONS_PER_SESSION}
        for tid, t in INTERVIEW_TRACKS.items()
    ]}


@app.post("/interview/start")
def interview_start(data: StartInterviewRequest, user=Depends(get_current_user)):
    track = INTERVIEW_TRACKS.get(data.track)
    if not track:
        raise HTTPException(status_code=400, detail="Unknown track. Choose from: " + ", ".join(INTERVIEW_TRACKS))
    picked = random.sample(track["questions"], min(QUESTIONS_PER_SESSION, len(track["questions"])))
    state = {
        "id": uuid.uuid4().hex,
        "email": user["email"],
        "track": data.track,
        "track_title": track["title"],
        "questions": picked,
        "index": 0,
        "answers": [],
        "status": "active",
        "summary": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    db_create_interview(state)
    return {
        "session_id": state["id"], "track": data.track, "track_title": track["title"],
        "status": "active", "current": public_question(state),
    }


@app.post("/interview/answer")
def interview_answer(data: AnswerRequest, user=Depends(get_current_user)):
    state = db_get_interview(data.session_id)
    if not state or state["email"] != user["email"]:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if state["status"] != "active":
        raise HTTPException(status_code=400, detail="This interview is already finished")
    if len(data.answer.strip()) < 3:
        raise HTTPException(status_code=400, detail="Please type an answer first")
    question = state["questions"][state["index"]]
    result = evaluate_answer(question, data.answer.strip())
    state["answers"].append({
        "question_id": question["id"], "question": question["q"],
        "answer": data.answer.strip(),
        "input_mode": "voice" if data.input_mode == "voice" else "text",
        **result,
    })
    state["index"] += 1
    finished = state["index"] >= len(state["questions"])
    if finished:
        state["status"] = "completed"
        state["summary"] = summarize(state)
    db_update_interview(state)
    return {
        "feedback": result,
        "finished": finished,
        "next": None if finished else public_question(state),
        "summary": state["summary"] if finished else None,
    }


@app.get("/interview/history")
def interview_history(user=Depends(get_current_user)):
    sessions = db_list_interviews(user["email"])
    return {"sessions": [{
        "session_id": s["id"], "track": s["track"], "track_title": s["track_title"],
        "status": s["status"],
        "overall_score": (s.get("summary") or {}).get("overall_score"),
        "questions_answered": len(s["answers"]),
        "created_at": s["created_at"],
    } for s in sessions]}


# ---------------------------------------------------------------------------
# Sprint 5: Readiness analytics + TPO overview
# Voice mode itself lives in the browser (Web Speech API): the interviewer
# reads questions aloud and answers are dictated into the same scoring flow,
# tagged input_mode="voice" per answer. Analytics below are computed from the
# stored session states, so no extra tables are needed.
# ---------------------------------------------------------------------------
from collections import Counter


def _sb_list_all(table: str):
    with httpx.Client(timeout=15) as client:
        res = client.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            params={"select": "*"},
        )
        res.raise_for_status()
        return res.json()


def db_list_all_users():
    if DB_ENABLED:
        return _sb_list_all("app_users")
    return list(users_db.values())


def db_list_all_interviews():
    if DB_ENABLED:
        return [row["state"] for row in _sb_list_all("app_interviews")]
    return list(interviews_db.values())


def _readiness_for(email: str, sessions: list) -> dict:
    """Readiness math shared by /dashboard/stats, /analytics/me and /tpo/overview:
    50 points from the ATS score + 50 from the average interview score."""
    last_ats = db_get_ats(email)
    completed = [s for s in sessions
                 if s.get("status") == "completed" and s.get("summary")]
    interview_avg = (sum(s["summary"]["overall_score"] for s in completed)
                     / len(completed)) if completed else None
    ats_score = last_ats["score"] if last_ats else 0
    readiness = 0
    if last_ats:
        readiness += round(ats_score * 0.5)
    if interview_avg is not None:
        readiness += round(interview_avg * 0.5)
    return {
        "ats_score": ats_score,
        "ats_points": round(ats_score * 0.5) if last_ats else 0,
        "interviews_completed": len(completed),
        "interview_avg": round(interview_avg) if interview_avg is not None else None,
        "interview_points": round(interview_avg * 0.5) if interview_avg is not None else 0,
        "readiness_score": readiness,
    }


@app.get("/analytics/me")
def my_analytics(user=Depends(get_current_user)):
    email = user["email"]
    sessions = db_list_interviews(email)
    base = _readiness_for(email, sessions)
    completed = sorted(
        [s for s in sessions if s.get("status") == "completed" and s.get("summary")],
        key=lambda s: s["created_at"],
    )

    trend = [{
        "date": s["created_at"], "track": s["track"],
        "track_title": s["track_title"],
        "score": s["summary"]["overall_score"],
    } for s in completed]

    by_track = {}
    for s in completed:
        slot = by_track.setdefault(s["track"], {
            "track": s["track"], "track_title": s["track_title"],
            "sessions": 0, "scores": [],
        })
        slot["sessions"] += 1
        slot["scores"].append(s["summary"]["overall_score"])
    track_stats = [{
        "track": t["track"], "track_title": t["track_title"],
        "sessions": t["sessions"],
        "avg_score": round(sum(t["scores"]) / len(t["scores"])),
        "best_score": max(t["scores"]),
    } for t in by_track.values()]

    missed = Counter()
    total_answers = 0
    total_words = 0
    voice_answers = 0
    for s in sessions:
        for a in s.get("answers", []):
            total_answers += 1
            total_words += a.get("word_count", 0)
            if a.get("input_mode") == "voice":
                voice_answers += 1
            for point in a.get("missed_points", []):
                missed[point] += 1
    recurring_gaps = [{"point": p, "times_missed": n}
                      for p, n in missed.most_common(5)]

    return {
        **base,
        "has_resume": db_get_resume(email) is not None,
        "trend": trend,
        "score_delta": (trend[-1]["score"] - trend[0]["score"]) if len(trend) >= 2 else None,
        "tracks": track_stats,
        "recurring_gaps": recurring_gaps,
        "practice": {
            "total_answers": total_answers,
            "total_words": total_words,
            "avg_words_per_answer": round(total_words / total_answers) if total_answers else 0,
            "voice_answers": voice_answers,
        },
    }


@app.get("/tpo/overview")
def tpo_overview(user=Depends(get_current_user)):
    if user.get("role") != "tpo":
        raise HTTPException(status_code=403,
                            detail="TPO view is available to placement-cell (TPO) accounts only")
    all_sessions = db_list_all_interviews()
    by_email = {}
    for s in all_sessions:
        by_email.setdefault(s["email"], []).append(s)

    students = []
    for u in db_list_all_users():
        if u.get("role") == "tpo":
            continue
        mine = by_email.get(u["email"], [])
        stats = _readiness_for(u["email"], mine)
        last_active = None
        if mine:
            last_active = max(s["created_at"] for s in mine)
        students.append({
            "name": u["name"], "email": u["email"],
            "has_resume": db_get_resume(u["email"]) is not None,
            **stats, "last_active": last_active,
        })
    students.sort(key=lambda s: s["readiness_score"], reverse=True)

    n = len(students)
    return {
        "cohort": {
            "total_students": n,
            "students_with_resume": sum(1 for s in students if s["has_resume"]),
            "students_interviewed": sum(1 for s in students if s["interviews_completed"] > 0),
            "total_interviews": sum(s["interviews_completed"] for s in students),
            "avg_readiness": round(sum(s["readiness_score"] for s in students) / n) if n else 0,
        },
        "students": students,
    }
