from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import tempfile
import io
import re

# Load env
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection - MUST use env vars
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# App and Router (all routes behind /api)
app = FastAPI()
api_router = APIRouter(prefix="/api")

# ---------- Models ----------
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

class CV(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    filename: str
    content_type: str
    raw_text: str
    sections: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    company: str
    location: str
    description: str
    requirements: List[str] = []
    preferred: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MatchRequest(BaseModel):
    session_id: Optional[str] = None
    cv_id: Optional[str] = None
    job_id: Optional[str] = None
    cv_text: Optional[str] = None
    job_description: Optional[str] = None

class CoverLetterRequest(BaseModel):
    session_id: str
    cv_id: str
    job_id: str
    tone: str = "formal"
    template: str = "classic"
    personal_note: Optional[str] = None
    model_provider: Optional[str] = None  # openai, anthropic, gemini
    model_name: Optional[str] = None

# ---------- Utilities ----------
STOPWORDS = set(
    "a,an,the,and,or,of,in,to,with,for,on,at,by,from,is,as,that,this,these,those,be,are,was,were,will,can,our,your,his,her,its,they,them,us,we,have,has,had,over,more,than,across,into,about,per,via".split(",")
)

def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\n\s]", " ", text.lower())

def tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\s+", normalize(text)) if t and t not in STOPWORDS]

async def seed_jobs_if_empty():
    count = await db.jobs.count_documents({})
    if count > 0:
        return
    samples = [
        Job(
            title="Full-Stack Engineer",
            company="Acme Corp",
            location="Remote",
            description=(
                "We are seeking a Full-Stack Engineer to build web applications using React,"
                " FastAPI, and MongoDB. Responsibilities include developing REST APIs,"
                " integrating third-party services, writing tests, and collaborating with designers."
            ),
            requirements=[
                "React",
                "FastAPI",
                "Python",
                "JavaScript",
                "MongoDB",
                "REST APIs",
                "Git",
                "Docker",
            ],
            preferred=["Kubernetes", "CI/CD", "Testing"],
        ).dict(),
        Job(
            title="Data Analyst",
            company="Insight Analytics",
            location="New York, NY",
            description=(
                "Analyze datasets, create dashboards, and communicate insights."
                " Proficiency in SQL, Python (pandas, numpy), and data visualization tools required."
            ),
            requirements=["SQL", "Python", "Pandas", "NumPy", "Data Visualization"],
            preferred=["PowerBI", "Tableau"],
        ).dict(),
        Job(
            title="Machine Learning Engineer",
            company="VisionAI",
            location="San Francisco, CA",
            description=(
                "Design, train, and deploy ML models. Experience with PyTorch or TensorFlow,"
                " MLOps, and cloud services."),
            requirements=["Python", "PyTorch", "TensorFlow", "MLOps", "Cloud"],
            preferred=["Kubernetes", "AWS", "GCP"],
        ).dict(),
    ]
    await db.jobs.insert_many(samples)

# Basic PDF/DOCX/TXT extraction

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text
        with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            return extract_text(tmp.name) or ""
    except Exception as e:
        logging.exception("PDF extraction failed")
        return ""

def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        import docx2txt
        with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            return docx2txt.process(tmp.name) or ""
    except Exception:
        logging.exception("DOCX extraction failed")
        return ""


def parse_sections(text: str) -> Dict[str, Any]:
    # Very lightweight heuristic parser
    lines = [l.strip() for l in text.splitlines()]
    sections = {"education": [], "experience": [], "skills": [], "certifications": [], "achievements": []}

    current = None
    buffer: List[str] = []
    def flush():
        nonlocal buffer, current
        if current and buffer:
            content = " ".join(buffer).strip()
            if current == "skills":
                # Split skills by comma or bullets
                skills = re.split(r",|•|\u2022|\|", content)
                sections["skills"] = [s.strip() for s in skills if s.strip()]
            else:
                sections[current].append(content)
        buffer = []

    header_map = {
        r"education": "education",
        r"work experience|experience|professional experience": "experience",
        r"skills|technical skills|key skills": "skills",
        r"certifications|licenses": "certifications",
        r"achievements|awards": "achievements",
    }

    for ln in lines:
        l = ln.lower()
        matched = None
        for pat, key in header_map.items():
            if re.fullmatch(pat, l) or re.match(fr"^{pat}[:\-]?$", l):
                matched = key
                break
        if matched:
            flush()
            current = matched
        else:
            if current:
                buffer.append(ln)
    flush()

    # If skills empty, infer top keywords
    if not sections["skills"]:
        toks = tokenize(text)
        freq: Dict[str, int] = {}
        for t in toks:
            freq[t] = freq.get(t, 0) + 1
        sections["skills"] = [t for t, c in sorted(freq.items(), key=lambda x: -x[1])[:15]]
    return sections


def compute_match(cv_sections: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    cv_text = " ".join([
        " ".join(cv_sections.get("education", [])),
        " ".join(cv_sections.get("experience", [])),
        ",".join(cv_sections.get("skills", [])),
        " ".join(cv_sections.get("certifications", [])),
        " ".join(cv_sections.get("achievements", [])),
    ])
    job_text = " ".join([job.get("description", ""), " ".join(job.get("requirements", [])), " ".join(job.get("preferred", []))])

    cv_tokens = set(tokenize(cv_text))
    job_tokens = set(tokenize(job_text))
    overlap = cv_tokens & job_tokens
    jaccard = (len(overlap) / len(cv_tokens | job_tokens)) if (cv_tokens or job_tokens) else 0.0

    skill_overlaps = []
    cv_skills = [s.lower().strip() for s in cv_sections.get("skills", [])]
    for req in job.get("requirements", []):
        r = req.lower().strip()
        if any(r == s or r in s or s in r for s in cv_skills):
            skill_overlaps.append(req)

    score = round(60 * jaccard + 40 * (len(skill_overlaps) / max(1, len(job.get("requirements", [])))), 3)
    return {
        "score": score,
        "overlap_keywords": sorted(list(overlap))[:50],
        "matched_skills": skill_overlaps,
    }

# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.dict())
    await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

@api_router.post("/cv/upload")
async def upload_cv(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
    # Validate
    filename = file.filename
    content_type = file.content_type or "application/octet-stream"
    data = await file.read()

    # Extract text
    text = ""
    if filename.lower().endswith(".pdf") or content_type == "application/pdf":
        text = extract_text_from_pdf(data)
    elif filename.lower().endswith(".docx"):
        text = extract_text_from_docx(data)
    elif filename.lower().endswith(".txt") or content_type.startswith("text/"):
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = data.decode("latin-1", errors="ignore")
    else:
        raise HTTPException(status_code=415, detail="Unsupported file type. Use PDF, DOCX, or TXT.")

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the uploaded file.")

    sections = parse_sections(text)
    cv = CV(
        session_id=session_id or str(uuid.uuid4()),
        filename=filename,
        content_type=content_type,
        raw_text=text,
        sections=sections,
    )
    await db.cvs.insert_one(cv.dict())
    return {"cv": cv.dict()}

@api_router.get("/jobs", response_model=List[Job])
async def list_jobs():
    await seed_jobs_if_empty()
    items = await db.jobs.find().to_list(100)
    return [Job(**it) for it in items]

@api_router.post("/match")
async def match_cv_job(body: MatchRequest):
    if body.cv_id and body.job_id:
        cv_doc = await db.cvs.find_one({"id": body.cv_id})
        if not cv_doc:
            raise HTTPException(status_code=404, detail="CV not found")
        job_doc = await db.jobs.find_one({"id": body.job_id})
        if not job_doc:
            raise HTTPException(status_code=404, detail="Job not found")
        result = compute_match(cv_doc.get("sections", {}), job_doc)
        return {"cv_id": body.cv_id, "job_id": body.job_id, "result": result}
    # Fallback free-form
    if body.cv_text and body.job_description:
        sections = parse_sections(body.cv_text)
        job = {"description": body.job_description, "requirements": [], "preferred": []}
        result = compute_match(sections, job)
        return {"cv_id": None, "job_id": None, "result": result}
    raise HTTPException(status_code=400, detail="Provide (cv_id & job_id) or (cv_text & job_description)")

@api_router.post("/cover-letter/generate")
async def generate_cover_letter(body: CoverLetterRequest):
    # Check key
    from dotenv import load_dotenv as _ld
    _ld(ROOT_DIR / '.env')
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        raise HTTPException(status_code=400, detail="EMERGENT_LLM_KEY not set in backend/.env. Please provide the universal key.")

    # Load CV and Job
    cv_doc = await db.cvs.find_one({"id": body.cv_id, "session_id": body.session_id})
    if not cv_doc:
        raise HTTPException(status_code=404, detail="CV not found for this session")
    job_doc = await db.jobs.find_one({"id": body.job_id})
    if not job_doc:
        raise HTTPException(status_code=404, detail="Job not found")

    # Prepare prompt
    cv_sections = cv_doc.get("sections", {})
    job_desc = job_doc.get("description", "")
    reqs = ", ".join(job_doc.get("requirements", []))
    prefs = ", ".join(job_doc.get("preferred", []))

    system_message = "You are an expert career assistant that writes concise, personalized cover letters."

    prompt = f"""
Write a {body.tone} cover letter using the classic professional format.
- Target role: {job_doc.get('title')} at {job_doc.get('company')} ({job_doc.get('location')})
- Job summary: {job_desc}
- Required skills: {reqs}
- Preferred: {prefs}
- Candidate education: {' | '.join(cv_sections.get('education', []))}
- Candidate experience: {' | '.join(cv_sections.get('experience', []))}
- Candidate skills: {', '.join(cv_sections.get('skills', []))}
- Certifications/Achievements: {' | '.join(cv_sections.get('certifications', []) + cv_sections.get('achievements', []))}
- Personal note to include (optional): {body.personal_note or ''}

Instructions:
- Open with a strong, tailored introduction mentioning the company and role.
- In 2 short paragraphs, map the candidate's experience and skills to the job's requirements.
- Add a brief line showing enthusiasm for the company's mission.
- Close with a confident call-to-action.
- Keep it under 250 words. British English.
"""

    # Use emergentintegrations LLM
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        logging.exception("emergentintegrations import failed")
        raise HTTPException(status_code=500, detail="LLM integration not available. Please install emergentintegrations.")

    # Initialize
    chat = LlmChat(
        api_key=emergent_key,
        session_id=f"cover-letter-{body.session_id}",
        system_message=system_message,
    )

    # Model selection (default gpt-4o-mini if not provided)
    if body.model_provider and body.model_name:
        chat = chat.with_model(body.model_provider, body.model_name)
    else:
        chat = chat.with_model("openai", "gpt-4o-mini")

    # Generate
    try:
        response_text = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logging.exception("LLM generation failed")
        raise HTTPException(status_code=502, detail=f"Cover letter generation failed: {str(e)[:200]}")

    # Save
    cover_id = str(uuid.uuid4())
    doc = {
        "id": cover_id,
        "session_id": body.session_id,
        "cv_id": body.cv_id,
        "job_id": body.job_id,
        "content": response_text,
        "tone": body.tone,
        "template": body.template,
        "created_at": datetime.utcnow(),
    }
    await db.cover_letters.insert_one(doc)
    return {"id": cover_id, "content": response_text}

# Include router and CORS
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def on_startup():
    try:
        await seed_jobs_if_empty()
        logging.info("Startup completed: jobs seeded if needed.")
    except Exception:
        logging.exception("Startup tasks failed")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()