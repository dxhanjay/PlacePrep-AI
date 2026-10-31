"""
PlacePrep AI - Backend (Sprint 1 + Sprint 2)
FastAPI: Health, Signup, Login (JWT), Me, Dashboard Stats,
         Resume Upload (PDF) + Text Extraction + ATS Scoring vs a Job Description
Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
NOTE: Users, resumes and ATS results are stored in memory so the app runs
      instantly anywhere. A later sprint connects Supabase Postgres
      (schema in /database/schema.sql) to make them permanent.
"""
import io
import os
import re
from datetime import datetime, timedelta
from typing import Optional

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
users_db = {}  # email -> user dict (Sprint 1 only)

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
    user = users_db.get(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.get("/")
def health():
    return {"status": "ok", "project": "PlacePrep AI", "sprint": 1}

@app.post("/auth/signup")
def signup(data: SignupRequest):
    if data.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = {
        "name": data.name, "email": data.email, "role": data.role,
        "hashed_password": pwd_context.hash(data.password),
        "created_at": datetime.utcnow().isoformat(),
    }
    users_db[data.email] = user
    return {"message": "Signup successful", "token": create_token(data.email),
            "user": {"name": user["name"], "email": user["email"], "role": user["role"]}}

@app.post("/auth/login")
def login(data: LoginRequest):
    user = users_db.get(data.email)
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
    last_ats = ats_db.get(email)
    has_resume = email in resumes_db
    if last_ats:
        weak = [f"Missing skill: {s}" for s in last_ats["missing_skills"][:3]]
        weak_topics = weak or ["No major skill gaps against your last JD"]
    elif has_resume:
        weak_topics = ["Run an ATS check against a job description"]
    else:
        weak_topics = ["Upload your resume to unlock your ATS score"]
    return {
        "user": user["name"],
        "ats_score": last_ats["score"] if last_ats else 0,
        "interviews_completed": 0, "readiness_score": 0,
        "has_resume": has_resume,
        "weak_topics": weak_topics,
        "recent_activity": []
    }


# ---------------------------------------------------------------------------
# Sprint 2: Resume upload + ATS scoring
# ---------------------------------------------------------------------------
resumes_db = {}  # email -> {filename, text, word_count, skills, uploaded_at}
ats_db = {}      # email -> last ATS analysis result

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
    resumes_db[user["email"]] = record
    ats_db.pop(user["email"], None)  # previous score no longer matches this resume
    return {
        "message": "Resume uploaded and parsed",
        "filename": record["filename"],
        "word_count": record["word_count"],
        "skills_detected": record["skills"],
        "uploaded_at": record["uploaded_at"],
    }


@app.get("/resume/me")
def my_resume(user=Depends(get_current_user)):
    record = resumes_db.get(user["email"])
    if not record:
        return {"has_resume": False}
    return {
        "has_resume": True,
        "filename": record["filename"],
        "word_count": record["word_count"],
        "skills_detected": record["skills"],
        "uploaded_at": record["uploaded_at"],
        "last_ats": ats_db.get(user["email"]),
    }


@app.post("/resume/ats")
def ats_check(data: ATSRequest, user=Depends(get_current_user)):
    record = resumes_db.get(user["email"])
    if not record:
        raise HTTPException(status_code=400, detail="Upload your resume first")
    if len(data.job_description.strip()) < 50:
        raise HTTPException(status_code=400, detail="Please paste a fuller job description (at least a paragraph)")
    result = analyze_resume(record["text"], data.job_description)
    result["filename"] = record["filename"]
    result["analyzed_at"] = datetime.utcnow().isoformat()
    ats_db[user["email"]] = result
    return result
