#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
## user_problem_statement: CV upload + mock jobs + matching + cover letter generation with universal LLM key

## backend:
  - task: "Root endpoint (/api/)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED: GET /api/ returns {\"message\":\"Hello World\"} as expected."
  - task: "Seed mock jobs and list endpoint (/api/jobs)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Implemented jobs model, seeding on startup, and /api/jobs route returning list."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED: GET /api/jobs returns 3 seeded jobs with all required fields (id, title, company, location, description, requirements, preferred). Jobs properly seeded on startup."
  - task: "CV upload and parsing (/api/cv/upload)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Supports PDF/DOCX/TXT via pdfminer.six and docx2txt; stores sections in Mongo with UUIDs."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED: POST /api/cv/upload works correctly with TXT files, returns cv.id and sections.skills array. Edge cases tested: unsupported file types return 415, empty files return 422."
  - task: "Matching engine (/api/match)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Jaccard + skill overlap scoring; works with stored ids or free-form text."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED: POST /api/match successfully processes cv_id and job_id, returns result.score (56.154), matched_skills, and overlap_keywords arrays as expected."
  - task: "Cover letter generation (/api/cover-letter/generate)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: false
        -agent: "main"
        -comment: "Requires EMERGENT_LLM_KEY in backend/.env and emergentintegrations installed. Added error message if key missing."
        -working: "NA"
        -agent: "testing"
        -comment: "✅ TESTED: Endpoint properly configured with /api prefix. EMERGENT_LLM_KEY not present in backend/.env, so marked as NA. Implementation ready for when key is provided."

## frontend:
  - task: "Base UI with Tailwind, CV upload, job pick, match score, cover letter UI"
    implemented: true
    working: true
    file: "/app/frontend/src/App.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Functional UI wired to backend via REACT_APP_BACKEND_URL."

## metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 0
  run_ui: false

## test_plan:
  current_focus:
    - "Backend testing completed successfully - all endpoints working"
    - "Frontend testing not performed per system limitations"
  stuck_tasks:
    - "None"
  test_all: false
  test_priority: "high_first"

## agent_communication:
    -agent: "main"
    -message: "Please run backend tests focusing on CV upload, jobs listing, and matching. For cover letter, only test if EMERGENT_LLM_KEY is set in backend/.env. No URL hardcoding; all calls use /api prefix and envs."
    -agent: "testing"
    -message: "Completed comprehensive backend testing. All core endpoints working correctly. Created backend_test.py with realistic test data. All 6 testable endpoints passed, cover letter marked NA due to missing EMERGENT_LLM_KEY."

#====================================================================================================