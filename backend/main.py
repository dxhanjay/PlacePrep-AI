"""
PlacePrep AI - Sprint 1 Backend
FastAPI: Health, Signup, Login (JWT), Me, Dashboard Stats (mock)
Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
NOTE: Sprint 1 uses in-memory users so you can run instantly.
      In Sprint 2 we connect Supabase Postgres (schema in /database/schema.sql)
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

app = FastAPI(title="PlacePrep AI API", version="1.0-sprint1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    # Mock data for Sprint 1 UI - real data from DB in Sprint 2/5
    return {
        "user": user["name"],
        "ats_score": 0, "interviews_completed": 0, "readiness_score": 0,
        "weak_topics": ["Add your resume in Sprint 2 to unlock this"],
        "recent_activity": []
    }
