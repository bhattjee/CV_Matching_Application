#!/usr/bin/env python3
"""
FastAPI Backend Server for CV Matching Application
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

app = FastAPI(title="CV Matching API")

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class MatchRequest(BaseModel):
    cv_id: str
    job_id: str

class CoverLetterRequest(BaseModel):
    session_id: str
    cv_id: str
    job_id: str
    tone: str = "formal"
    template: str = "classic"

# Sample data
SAMPLE_JOBS = [
    {
        "id": "job_1",
        "title": "Senior Software Engineer",
        "company": "TechCorp",
        "location": "San Francisco, CA",
        "description": "We are looking for a senior software engineer to join our team.",
        "requirements": ["Python", "JavaScript", "React", "FastAPI", "MongoDB"],
        "preferred": ["Docker", "Kubernetes", "AWS"]
    },
    {
        "id": "job_2",
        "title": "Full Stack Developer",
        "company": "StartupXYZ",
        "location": "Remote",
        "description": "Join our fast-growing startup as a full stack developer.",
        "requirements": ["JavaScript", "React", "Node.js", "SQL"],
        "preferred": ["TypeScript", "GraphQL", "AWS"]
    }
]

# In-memory storage
cv_storage = {}
cover_letter_storage = {}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Hello World"}

@app.get("/api/")
async def api_root():
    """API health check endpoint"""
    return {"message": "Hello World"}

@app.get("/api/jobs")
async def get_jobs():
    """Retrieve all available job postings"""
    return SAMPLE_JOBS

@app.post("/api/cv/upload")
async def upload_cv(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """Upload and parse CV document"""
    
    # Check file type
    allowed_extensions = ['.txt', '.pdf', '.docx']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    
    # Read file content
    content = await file.read()
    
    if not content or len(content) == 0:
        raise HTTPException(status_code=422, detail="Empty file")
    
    # Parse CV content (simple text parsing for TXT files)
    text_content = content.decode('utf-8', errors='ignore')
    
    # Extract sections
    sections = {
        "skills": extract_skills(text_content),
        "education": extract_education(text_content),
        "experience": extract_experience(text_content)
    }
    
    # Generate CV ID
    cv_id = f"cv_{len(cv_storage) + 1}"
    
    # Store CV
    cv_storage[cv_id] = {
        "id": cv_id,
        "filename": file.filename,
        "content": text_content,
        "sections": sections,
        "session_id": session_id
    }
    
    return {"cv": cv_storage[cv_id]}

@app.post("/api/match")
async def match_cv_to_job(request: MatchRequest):
    """Match CV against job posting"""
    
    if request.cv_id not in cv_storage:
        raise HTTPException(status_code=404, detail="CV not found")
    
    cv = cv_storage[request.cv_id]
    job = next((j for j in SAMPLE_JOBS if j["id"] == request.job_id), None)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Calculate match score
    cv_skills = set(cv["sections"].get("skills", []))
    job_requirements = set(job["requirements"])
    
    matched_skills = list(cv_skills & job_requirements)
    overlap_keywords = matched_skills.copy()
    
    # Calculate score
    if len(job_requirements) > 0:
        score = (len(matched_skills) / len(job_requirements)) * 100
    else:
        score = 0
    
    return {
        "result": {
            "score": round(score, 2),
            "matched_skills": matched_skills,
            "overlap_keywords": overlap_keywords
        }
    }

@app.post("/api/cover-letter/generate")
async def generate_cover_letter(request: CoverLetterRequest):
    """Generate AI-powered cover letter"""
    
    # Check if EMERGENT_LLM_KEY is present
    if not os.getenv("EMERGENT_LLM_KEY"):
        raise HTTPException(status_code=503, detail="LLM service not configured")
    
    if request.cv_id not in cv_storage:
        raise HTTPException(status_code=404, detail="CV not found")
    
    job = next((j for j in SAMPLE_JOBS if j["id"] == request.job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    cv = cv_storage[request.cv_id]
    
    # Generate simple cover letter (placeholder for AI generation)
    cover_letter_content = f"""
Dear Hiring Manager,

I am writing to express my interest in the {job['title']} position at {job['company']}.

Based on my background and skills, I believe I would be a great fit for this role. 
I have experience with {', '.join(cv['sections'].get('skills', ['various technologies']))}.

I look forward to the opportunity to discuss how I can contribute to your team.

Best regards
"""
    
    # Generate cover letter ID
    cover_letter_id = f"cl_{len(cover_letter_storage) + 1}"
    
    # Store cover letter
    cover_letter_storage[cover_letter_id] = {
        "id": cover_letter_id,
        "content": cover_letter_content.strip(),
        "cv_id": request.cv_id,
        "job_id": request.job_id
    }
    
    return cover_letter_storage[cover_letter_id]

# Helper functions
def extract_skills(text: str) -> List[str]:
    """Extract skills from CV text"""
    skills_section = re.search(r'SKILLS[:\s]*(.*?)(?:CERTIFICATIONS|EXPERIENCE|EDUCATION|$)', text, re.IGNORECASE | re.DOTALL)
    if skills_section:
        skills_text = skills_section.group(1)
        # Split by common delimiters
        skills = re.split(r'[,,\n\-•]', skills_text)
        return [s.strip() for s in skills if s.strip()]
    return []

def extract_education(text: str) -> List[str]:
    """Extract education from CV text"""
    education_section = re.search(r'EDUCATION[:\s]*(.*?)(?:EXPERIENCE|SKILLS|CERTIFICATIONS|$)', text, re.IGNORECASE | re.DOTALL)
    if education_section:
        return [education_section.group(1).strip()]
    return []

def extract_experience(text: str) -> List[str]:
    """Extract experience from CV text"""
    experience_section = re.search(r'EXPERIENCE[:\s]*(.*?)(?:EDUCATION|SKILLS|CERTIFICATIONS|$)', text, re.IGNORECASE | re.DOTALL)
    if experience_section:
        return [experience_section.group(1).strip()]
    return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
