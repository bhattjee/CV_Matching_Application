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
from contextlib import asynccontextmanager
import re
from openai import OpenAI
import magic

# Load env
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize DeepInfra client
deepinfra_client = OpenAI(
    api_key=os.environ.get("DEEPINFRA_API_KEY"),
    base_url="https://api.deepinfra.com/v1/openai",
)

# Router (all routes behind /api)
api_router = APIRouter(prefix="/api")

# Initialize file type detector
file_type_detector = magic.Magic(mime=True)

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

# ---------- File Processing ----------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text
        from io import BytesIO
        
        try:
            text = extract_text(BytesIO(file_bytes))
            if text.strip(): 
                return text
        except Exception as e:
            logging.warning(f"PDF direct extraction failed: {str(e)}")

        with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            text = extract_text(tmp.name)
            if not text.strip():
                raise ValueError("Extracted empty text")
            return text
            
    except Exception as e:
        logging.error(f"PDF extraction error: {str(e)}")
        return ""

def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        import docx2txt
        from io import BytesIO
        
        try:
            text = docx2txt.process(BytesIO(file_bytes))
            if text.strip(): 
                return text
        except Exception as e:
            logging.warning(f"DOCX direct extraction failed: {str(e)}")
            
        with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            text = docx2txt.process(tmp.name)
            if not text.strip():
                raise ValueError("Extracted empty text")
            return text
            
    except Exception as e:
        logging.error(f"DOCX extraction error: {str(e)}")
        return ""

def extract_text_from_txt(file_bytes: bytes) -> str:
    encodings = ['utf-8', 'latin-1', 'windows-1252', 'ascii']
    for encoding in encodings:
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""

def get_file_type(file_bytes: bytes) -> str:
    try:
        return file_type_detector.from_buffer(file_bytes)
    except Exception:
        return "application/octet-stream"

def parse_sections(text: str) -> Dict[str, Any]:
    lines = [l.strip() for l in text.splitlines()]
    sections = {"education": [], "experience": [], "skills": [], "certifications": [], "achievements": []}

    current = None
    buffer: List[str] = []
    
    def flush():
        nonlocal buffer, current
        if current and buffer:
            content = " ".join(buffer).strip()
            if current == "skills":
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
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    
    filename = file.filename.lower()
    data = await file.read()
    
    if not data:
        raise HTTPException(400, "Empty file uploaded")

    content_type = get_file_type(data)
    logging.info(f"Uploading file: {filename}, detected type: {content_type}")

    valid_types = {
        'application/pdf': extract_text_from_pdf,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': extract_text_from_docx,
        'text/plain': extract_text_from_txt
    }
    
    extractor = None
    for mime, func in valid_types.items():
        if mime in content_type:
            extractor = func
            break
        if filename.endswith(mime.split('/')[-1].split('.')[-1]):
            extractor = func
            break

    if not extractor:
        raise HTTPException(415, "Unsupported file type. Use PDF, DOCX, or TXT")

    text = extractor(data)
    if not text.strip():
        if content_type == 'application/pdf':
            try:
                from pdf2image import convert_from_bytes
                import pytesseract
                images = convert_from_bytes(data)
                text = "\n".join(pytesseract.image_to_string(img) for img in images)
                if not text.strip():
                    raise HTTPException(422, "Could not extract text - file may be image-based")
            except ImportError:
                logging.warning("OCR dependencies not installed")
                raise HTTPException(422, "Could not extract text - install OCR dependencies for image-based PDFs")
            except Exception as e:
                logging.error(f"OCR failed: {str(e)}")
                raise HTTPException(422, "OCR processing failed")

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
    logger.info("Jobs endpoint accessed")
    try:
        await seed_jobs_if_empty()
        items = await db.jobs.find().to_list(100)
        logger.info(f"Found {len(items)} jobs")
        return [Job(**it) for it in items]
    except Exception as e:
        logger.error(f"Error fetching jobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")

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
    if body.cv_text and body.job_description:
        sections = parse_sections(body.cv_text)
        job = {"description": body.job_description, "requirements": [], "preferred": []}
        result = compute_match(sections, job)
        return {"cv_id": None, "job_id": None, "result": result}
    raise HTTPException(status_code=400, detail="Provide (cv_id & job_id) or (cv_text & job_description)")

@api_router.post("/cover-letter/generate")
async def generate_cover_letter(body: CoverLetterRequest):
    cv_doc = await db.cvs.find_one({"id": body.cv_id, "session_id": body.session_id})
    if not cv_doc:
        raise HTTPException(status_code=404, detail="CV not found for this session")
    job_doc = await db.jobs.find_one({"id": body.job_id})
    if not job_doc:
        raise HTTPException(status_code=404, detail="Job not found")

    cv_sections = cv_doc.get("sections", {})
    job_desc = job_doc.get("description", "")
    reqs = ", ".join(job_doc.get("requirements", []))
    prefs = ", ".join(job_doc.get("preferred", []))

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

    try:
        response = deepinfra_client.chat.completions.create(
            model="mistralai/Mistral-7B-Instruct-v0.3",
            messages=[
                {"role": "system", "content": "You are an expert career assistant that writes concise, personalized cover letters."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        response_text = response.choices[0].message.content
    except Exception as e:
        logging.exception("LLM generation failed")
        raise HTTPException(status_code=502, detail=f"Cover letter generation failed: {str(e)[:200]}")

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

# ---------- App Setup ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting server...")
    try:
        await seed_jobs_if_empty()
        test_text = "Test text extraction"
        assert extract_text_from_txt(test_text.encode('utf-8')) == test_text
    except Exception as e:
        logging.error(f"Startup failed: {str(e)}")
        raise
    yield
    logging.info("Shutting down server...")
    client.close()

app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)