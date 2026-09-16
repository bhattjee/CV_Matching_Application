# CV_Host - CV Matching Application

A web application for matching CVs (resumes) to job postings with AI-powered analysis and cover letter generation.

## Overview

CV_Host is a full-stack application that allows users to:
- Upload and parse CV/resume documents (TXT, PDF, DOCX formats)
- Browse available job postings
- Match CVs against job requirements with scoring
- Generate AI-powered cover letters

## Tech Stack

### Backend
- **Framework**: FastAPI 0.110.1
- **Server**: Uvicorn 0.25.0
- **Database**: MongoDB (via PyMongo 4.5.0 and Motor 3.3.1)
- **Authentication**: JWT (python-jose, PyJWT, passlib)
- **Document Processing**: pdfminer.six, docx2txt
- **Data Processing**: pandas, numpy
- **Cloud Services**: boto3 (AWS SDK)
- **LLM Integration**: emergentintegrations (via private PyPI index)

### Frontend
- **Build Tool**: Vite
- **Package Manager**: Yarn

## Project Structure

```
CV_Host/
├── backend/
│   ├── .env                 # Environment variables (contains sensitive data)
│   ├── requirements.txt     # Python dependencies
│   └── __pycache__/         # Compiled Python files
├── tests/
│   └── __init__.py
├── backend_test.py          # API testing suite
├── package-lock.json        # Node.js dependencies
├── yarn.lock                # Yarn lockfile
├── LICENSE                  # MIT License
└── README.md                # This file
```

## Installation

### Backend Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Configure environment variables in `backend/.env`:
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="your_database_name"
CORS_ORIGINS="http://localhost:5173"
DEEPINFRA_API_KEY="your_api_key_here"
```

### Frontend Setup

1. Install dependencies:
```bash
yarn install
```

2. Start development server:
```bash
yarn dev
```

## API Endpoints

Based on the test suite, the following endpoints are available:

- `GET /api/` - Health check endpoint
- `GET /api/jobs` - Retrieve available job postings
- `POST /api/cv/upload` - Upload and parse CV documents
- `POST /api/match` - Match CV against a job posting
- `POST /api/cover-letter/generate` - Generate AI-powered cover letters

## Testing

Run the backend test suite:

```bash
python backend_test.py
```

The test suite covers:
- Root endpoint health check
- Jobs retrieval
- CV upload (success case, unsupported file types, empty files)
- CV-to-job matching
- Cover letter generation (if LLM API key is configured)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security Notes

⚠️ **IMPORTANT**: The `.env` file contains sensitive configuration data including API keys. Ensure this file is:
- Added to `.gitignore`
- Never committed to version control
- Properly secured in production environments
