#!/usr/bin/env python3
"""
Backend API Testing Suite for CV Matching Application
Tests all backend endpoints with realistic data and edge cases
"""

import requests
import json
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')
BASE_URL = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')
API_BASE = f"{BASE_URL}/api"

print(f"Testing backend at: {API_BASE}")

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.cv_id = None
        self.job_id = None
        
    def log_result(self, test_name, success, details=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details
        })
        
    def test_root_endpoint(self):
        """Test GET /api/ endpoint"""
        try:
            response = self.session.get(f"{API_BASE}/")
            if response.status_code == 200:
                data = response.json()
                if data.get('message') == 'Hello World':
                    self.log_result("GET /api/ returns Hello World", True)
                    return True
                else:
                    self.log_result("GET /api/ wrong message", False, f"Got: {data}")
                    return False
            else:
                self.log_result("GET /api/ status code", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("GET /api/ connection", False, str(e))
            return False
            
    def test_jobs_endpoint(self):
        """Test GET /api/jobs endpoint"""
        try:
            response = self.session.get(f"{API_BASE}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                if len(jobs) >= 1:
                    job = jobs[0]
                    required_fields = ['id', 'title', 'company', 'location', 'description', 'requirements', 'preferred']
                    missing_fields = [field for field in required_fields if field not in job]
                    
                    if not missing_fields:
                        # Store first job ID for matching test
                        self.job_id = job['id']
                        self.log_result("GET /api/jobs returns valid jobs", True, f"Found {len(jobs)} jobs")
                        return True
                    else:
                        self.log_result("GET /api/jobs missing fields", False, f"Missing: {missing_fields}")
                        return False
                else:
                    self.log_result("GET /api/jobs empty response", False, "No jobs returned")
                    return False
            else:
                self.log_result("GET /api/jobs status code", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("GET /api/jobs connection", False, str(e))
            return False
            
    def test_cv_upload_success(self):
        """Test POST /api/cv/upload with valid TXT file"""
        try:
            # Create realistic CV content
            cv_content = """John Smith
Software Engineer

EDUCATION
Bachelor of Science in Computer Science
University of Technology, 2020

EXPERIENCE
Software Developer at TechCorp (2020-2023)
- Developed web applications using React and Python
- Built REST APIs with FastAPI
- Worked with MongoDB databases
- Implemented CI/CD pipelines

SKILLS
Python, JavaScript, React, FastAPI, MongoDB, Docker, Git, REST APIs, SQL

CERTIFICATIONS
AWS Certified Developer Associate
"""
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(cv_content)
                temp_path = f.name
                
            try:
                with open(temp_path, 'rb') as f:
                    files = {'file': ('john_smith_cv.txt', f, 'text/plain')}
                    data = {'session_id': 'test_session_123'}
                    
                    response = self.session.post(f"{API_BASE}/cv/upload", files=files, data=data)
                    
                if response.status_code == 200:
                    result = response.json()
                    cv_data = result.get('cv', {})
                    
                    if 'id' in cv_data and 'sections' in cv_data:
                        sections = cv_data['sections']
                        if 'skills' in sections and isinstance(sections['skills'], list):
                            self.cv_id = cv_data['id']
                            self.log_result("POST /api/cv/upload success", True, f"CV ID: {self.cv_id}")
                            return True
                        else:
                            self.log_result("POST /api/cv/upload missing skills", False, "No skills array found")
                            return False
                    else:
                        self.log_result("POST /api/cv/upload missing fields", False, "Missing id or sections")
                        return False
                else:
                    self.log_result("POST /api/cv/upload status code", False, f"Status: {response.status_code}, Response: {response.text}")
                    return False
                    
            finally:
                os.unlink(temp_path)
                
        except Exception as e:
            self.log_result("POST /api/cv/upload error", False, str(e))
            return False
            
    def test_cv_upload_unsupported_file(self):
        """Test POST /api/cv/upload with unsupported file type (should return 415)"""
        try:
            # Create a fake image file
            fake_image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            
            files = {'file': ('test.png', fake_image_content, 'image/png')}
            data = {'session_id': 'test_session_123'}
            
            response = self.session.post(f"{API_BASE}/cv/upload", files=files, data=data)
            
            if response.status_code == 415:
                self.log_result("POST /api/cv/upload unsupported file type", True, "Correctly returned 415")
                return True
            else:
                self.log_result("POST /api/cv/upload unsupported file type", False, f"Expected 415, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("POST /api/cv/upload unsupported file error", False, str(e))
            return False
            
    def test_cv_upload_empty_file(self):
        """Test POST /api/cv/upload with empty text file (should return 422)"""
        try:
            # Create empty text file
            files = {'file': ('empty.txt', b'', 'text/plain')}
            data = {'session_id': 'test_session_123'}
            
            response = self.session.post(f"{API_BASE}/cv/upload", files=files, data=data)
            
            if response.status_code == 422:
                self.log_result("POST /api/cv/upload empty file", True, "Correctly returned 422")
                return True
            else:
                self.log_result("POST /api/cv/upload empty file", False, f"Expected 422, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("POST /api/cv/upload empty file error", False, str(e))
            return False
            
    def test_match_endpoint(self):
        """Test POST /api/match endpoint"""
        if not self.cv_id or not self.job_id:
            self.log_result("POST /api/match prerequisites", False, "Missing CV ID or Job ID from previous tests")
            return False
            
        try:
            payload = {
                'cv_id': self.cv_id,
                'job_id': self.job_id
            }
            
            response = self.session.post(f"{API_BASE}/match", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                match_result = result.get('result', {})
                
                required_fields = ['score', 'matched_skills', 'overlap_keywords']
                missing_fields = [field for field in required_fields if field not in match_result]
                
                if not missing_fields:
                    score = match_result['score']
                    if isinstance(score, (int, float)) and 0 <= score <= 100:
                        self.log_result("POST /api/match success", True, f"Score: {score}")
                        return True
                    else:
                        self.log_result("POST /api/match invalid score", False, f"Score: {score}")
                        return False
                else:
                    self.log_result("POST /api/match missing fields", False, f"Missing: {missing_fields}")
                    return False
            else:
                self.log_result("POST /api/match status code", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("POST /api/match error", False, str(e))
            return False
            
    def test_cover_letter_endpoint(self):
        """Test POST /api/cover-letter/generate endpoint (only if EMERGENT_LLM_KEY is present)"""
        # Check if EMERGENT_LLM_KEY exists in backend/.env
        backend_env_path = '/app/backend/.env'
        emergent_key_present = False
        
        try:
            with open(backend_env_path, 'r') as f:
                content = f.read()
                if 'EMERGENT_LLM_KEY' in content and not content.split('EMERGENT_LLM_KEY')[1].split('\n')[0].strip().strip('=').strip('"').strip("'") == '':
                    emergent_key_present = True
        except Exception:
            pass
            
        if not emergent_key_present:
            self.log_result("POST /api/cover-letter/generate", "NA", "EMERGENT_LLM_KEY not present in backend/.env")
            return "NA"
            
        if not self.cv_id or not self.job_id:
            self.log_result("POST /api/cover-letter/generate prerequisites", False, "Missing CV ID or Job ID from previous tests")
            return False
            
        try:
            payload = {
                'session_id': 'test_session_123',
                'cv_id': self.cv_id,
                'job_id': self.job_id,
                'tone': 'formal',
                'template': 'classic'
            }
            
            response = self.session.post(f"{API_BASE}/cover-letter/generate", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                if 'id' in result and 'content' in result:
                    self.log_result("POST /api/cover-letter/generate success", True, f"Generated cover letter ID: {result['id']}")
                    return True
                else:
                    self.log_result("POST /api/cover-letter/generate missing fields", False, "Missing id or content")
                    return False
            else:
                self.log_result("POST /api/cover-letter/generate status code", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("POST /api/cover-letter/generate error", False, str(e))
            return False
            
    def run_all_tests(self):
        """Run all backend tests in sequence"""
        print("=" * 60)
        print("BACKEND API TESTING SUITE")
        print("=" * 60)
        
        tests = [
            self.test_root_endpoint,
            self.test_jobs_endpoint,
            self.test_cv_upload_success,
            self.test_cv_upload_unsupported_file,
            self.test_cv_upload_empty_file,
            self.test_match_endpoint,
            self.test_cover_letter_endpoint
        ]
        
        for test in tests:
            test()
            print()
            
        # Summary
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r['success'] is True)
        failed = sum(1 for r in self.test_results if r['success'] is False)
        na = sum(1 for r in self.test_results if r['success'] == "NA")
        
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"N/A: {na}")
        
        if failed > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if result['success'] is False:
                    print(f"- {result['test']}: {result['details']}")
                    
        return failed == 0

if __name__ == "__main__":
    tester = BackendTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)