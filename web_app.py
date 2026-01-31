import sys
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from database import db
import uvicorn
import subprocess
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add current directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from linkedin_scraper import LinkedInScraper

app = FastAPI(title="LinkedIn Job Filter Tool")

# CORS (allow all for local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes that don't need auth
# We allow the frontend shell to load, JS will handle the UI-level redirect.
# All sensitive data APIs remain strictly protected.
PUBLIC_ROUTES = ["/api/auth/config", "/login", "/login.html", "/js/auth.js", "/favicon.ico", "/", "/index.html"]

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    
    # 1. Allow explicit public routes
    if path in PUBLIC_ROUTES:
        return await call_next(request)
    
    # 2. Allow static assets (CSS, Images, and non-sensitive JS)
    # We allow all .js now but stay vigilant on /api
    if path.endswith((".css", ".png", ".jpg", ".svg", ".ico", ".js")):
         return await call_next(request)

    # 3. Protect all other routes (especially /api/*)
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # If it's an API call, return 401
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        
        # For other page loads, redirect to login
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")

    token = auth_header.split(" ")[1]
    
    # Verify token with Supabase Auth
    try:
        user_res = db.client.auth.get_user(token)
        if not user_res or not user_res.user:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        # Optionally attach user to request state
        request.state.user = user_res.user
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Authentication failed"})

    return await call_next(request)

@app.get("/api/auth/config")
def get_auth_config():
    """Public endpoint to provide Supabase URL and Anon Key to frontend."""
    return {
        "url": os.environ.get("SUPABASE_URL"),
        # Serve the Anon Key to the browser, fallback to general key
        "key": os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")
    }

@app.get("/login", response_class=HTMLResponse)
def get_login_page():
    """Serve the login page at a pretty URL."""
    try:
        with open("static/login.html", "r") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading login page: {str(e)}")

# Global State
class ScraperState:
    running = False
    logs = []
    scraped_jobs = []
    total_found = 0
    total_dismissed = 0
    stop_event = threading.Event()
    scraper_instance = None
    active_history_id = None

state = ScraperState()
log_lock = threading.Lock()

# Models
class CandidateUpdate(BaseModel):
    pp_id: str
    corrected_name: str

class OverrideRequest(BaseModel):
    query: str
    pp_id: Optional[str] = None

class SearchParams(BaseModel):
    keywords: str
    location: str
    time_range: str = "all" # all, 24h, week, month
    limit: int = 25
    easy_apply: bool = False
    relevant: bool = False
    workplace_type: List[int] = []

class BlocklistUpdate(BaseModel):
    filename: str # "blocklist.txt" or "blocklist_companies.txt"
    content: str

class SettingsUpdate(BaseModel):
    linkedin_cookie: Optional[str] = None
    page_delay: Optional[float] = None
    job_delay: Optional[float] = None

class BlocklistValidate(BaseModel):
    items: List[str]

class SavedSearchRequest(BaseModel):
    name: str
    keywords: str = ""
    location: str = "Canada"
    time_range: str = "all"
    limit: int = 25
    easy_apply: bool = False
    relevant: bool = False
    workplace_type: List[int] = []

# --- Helper Functions ---

def get_user_id(request: Request) -> str:
    """Extract user_id from authenticated request."""
    if hasattr(request.state, 'user') and request.state.user:
        return request.state.user.id
    return None

def log_message(msg: str, history_id: str = None):
    """Log to in-memory state and optionally persist to Supabase."""
    with log_lock:
        state.logs.append(msg)
        if len(state.logs) > 500:
            state.logs.pop(0)
    
    # Persist to DB if history_id provided
    if history_id:
        db.log_search_event(history_id, msg)
    elif state.active_history_id:
        db.log_search_event(state.active_history_id, msg)
            
class LogInterceptor:
    """Redirect stdout to our log buffer."""
    def __init__(self):
        self.terminal = sys.__stdout__

    def write(self, text):
        if text.strip():
            log_message(text.strip())
        self.terminal.write(text)

    def flush(self):
        self.terminal.flush()
        
    def isatty(self):
        return getattr(self.terminal, 'isatty', lambda: False)()
        
    @property
    def encoding(self):
        return getattr(self.terminal, 'encoding', 'utf-8')

# --- Scraper Runner Thread ---

def run_scraper_thread(params: SearchParams, user_id: str = None):
    state.running = True
    state.stop_event.clear()
    state.scraped_jobs = []
    state.logs = [] # Clear logs on new run
    log_message("🧹 Initializing scraper session...")
    state.total_found = 0
    state.total_dismissed = 0
    
    # Log search start to history
    history_id = None
    if user_id:
        history_id = db.log_search_start(user_id, {
            "keywords": params.keywords,
            "location": params.location,
            "time_range": params.time_range
        })
    
    log_message("🚀 Starting Scraper Background Thread...")
    
    # Read user settings (including cookie and delays)
    user_cookie = None
    page_delay = 2.0
    job_delay = 1.0
    
    if user_id:
        settings = db.get_user_settings(user_id)
        if settings:
            user_cookie = settings.get('linkedin_cookie')
            page_delay = settings.get('page_delay', 2.0)
            job_delay = settings.get('job_delay', 1.0)
            if user_cookie:
                log_message("🔑 Using user-provided LinkedIn cookie and rate limits from settings")
    
    # Read blocklists from Supabase (user-specific)
    try:
        block_titles = db.get_blocklist("job_title", user_id)
        block_companies = db.get_blocklist("company_linkedin", user_id)
    except Exception as e:
        log_message(f"⚠️ Error reading blocklists from Supabase: {e}")
        block_titles = []
        block_companies = []

    # Initialize Scraper
    total_found = 0
    total_dismissed = 0
    total_skipped = 0
    status = "completed"
    
    try:
        scraper = LinkedInScraper(
            keywords=params.keywords,
            location=params.location,
            limit_jobs=params.limit,
            dismiss_keywords=block_titles,
            dismiss_companies=block_companies,
            relevant=params.relevant,
            time_filter=params.time_range,
            easy_apply=params.easy_apply,
            workplace_type=params.workplace_type,
            user_id=user_id,
            cookie_string=user_cookie,
            page_delay=page_delay,
            job_delay=job_delay,
            history_id=history_id
        )
        state.scraper_instance = scraper
        
        # Run processing
        results = scraper.process_jobs()
        if results:
            total_found, total_dismissed, total_skipped = results
            
    except Exception as e:
        log_message(f"❌ Scraper crashed: {e}")
        status = "failed"
    finally:
        if state.scraper_instance:
            state.scraper_instance.close_session()
        state.running = False
        state.active_history_id = None
        log_message("🛑 Scraper finished.")
        
        # Log search completion
        if history_id:
            db.log_search_complete(history_id, total_found, total_dismissed, total_skipped, status)

# Redirect stdout globally (Affects entire process)
sys.stdout = LogInterceptor()

# --- API Endpoints ---

@app.post("/api/start")
def start_scraper(params: SearchParams, request: Request):
    if state.running:
        raise HTTPException(status_code=400, detail="Scraper is already running")
    
    user_id = get_user_id(request) # Ensure user_id is defined
    history_id = db.log_search_start(user_id, params.dict())
    state.active_history_id = history_id
    
    thread = threading.Thread(target=run_scraper_thread, args=(params, user_id, history_id))
    thread.daemon = True
    thread.start()
    return {"status": "started"}

@app.post("/api/stop")
def stop_scraper():
    # Since we can't easily stop the thread safely without modifying the Scraper class,
    # we'll just set a flag (though the current scraper doesn't check it).
    # This is a placeholder for future improvement. 
    # Realistically, user might just have to wait for the page limit/job limit to hit.
    if not state.running:
        return {"status": "not_running"}
    
    state.stop_event.set() 
    # Force close session? Might cause warnings but could stop it.
    if state.scraper_instance and hasattr(state.scraper_instance, 'session'):
         state.scraper_instance.session.close()
         log_message("⚠️ Force closing session to stop scraper...")
    
    return {"status": "stopping_initiated"}

@app.get("/api/status")
def get_status():
    return {
        "running": state.running,
        "logs": state.logs[-50:], # Send last 50 logs
        "total_found": state.total_found # TODO: Update this real-time if possible
    }

@app.get("/api/config")
def get_config():
    # Return defaults from config.py if it exists, or hardcoded
    try:
        import config
    except ImportError:
        return {}
    except Exception as e:
        return {
            "keywords": "",
            "location": "Canada",
            "time_range": "all",
            "limit": 25
        }
    
    return {
        "keywords": getattr(config, "KEYWORDS", ""),
        "location": getattr(config, "LOCATION", "Canada"),
        "time_range": getattr(config, "TIME_RANGE", "r86400"),
        "limit": getattr(config, "LIMIT_JOBS", 25)
    }

@app.get("/api/blocklist")
def get_blocklist(filename: str, request: Request):
    user_id = get_user_id(request)
    name = "job_title" if filename == "blocklist.txt" else "company_linkedin"
    items = db.get_blocklist(name, user_id)
    return {"content": "\n".join(items)}

@app.post("/api/blocklist")
def save_blocklist(update: BlocklistUpdate, request: Request):
    user_id = get_user_id(request)
    name = "job_title" if update.filename == "blocklist.txt" else "company_linkedin"
    items = update.content.split("\n")
    try:
        db.update_blocklist(name, items, user_id)
        return {"status": "saved"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/history")
def get_history(request: Request, limit: int = 50, offset: int = 0):
    user_id = get_user_id(request)
    data = db.get_history(limit, offset, user_id)
    total = db.get_history_count(user_id)
    return {
        "items": data,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/api/settings")
def get_settings(request: Request):
    user_id = get_user_id(request)
    settings = db.get_user_settings(user_id)
    if settings:
        cookie = settings.get('linkedin_cookie', '')
        return {
            "has_cookie": bool(cookie),
            "cookie_preview": f"...{cookie[-20:]}" if len(cookie) > 20 else cookie,
            "linkedin_cookie": cookie,
            "page_delay": settings.get('page_delay', 2.0),
            "job_delay": settings.get('job_delay', 1.0),
            "updated_at": settings.get('updated_at')
        }
    return {
        "has_cookie": False, 
        "cookie_preview": None, 
        "linkedin_cookie": "", 
        "page_delay": 2.0, 
        "job_delay": 1.0, 
        "updated_at": None
    }

@app.post("/api/settings")
def save_settings(update: SettingsUpdate, request: Request):
    user_id = get_user_id(request)
    # Get current settings to maintain values if not provided in update
    current = db.get_user_settings(user_id) or {}
    
    cookie = update.linkedin_cookie if update.linkedin_cookie is not None else current.get('linkedin_cookie')
    page_delay = update.page_delay if update.page_delay is not None else current.get('page_delay', 2.0)
    job_delay = update.job_delay if update.job_delay is not None else current.get('job_delay', 1.0)
    
    success = db.save_user_settings(user_id, cookie, page_delay, job_delay)
    if success:
        return {"status": "saved"}
    raise HTTPException(status_code=500, detail="Failed to save settings to database")

@app.post("/api/blocklist/validate")
def validate_blocklist(req: BlocklistValidate):
    seen = set()
    duplicates = []
    whitespace_issues = []
    
    for i, original in enumerate(req.items):
        stripped = original.strip()
        
        # Check Whitespace
        if original != stripped:
            whitespace_issues.append({"index": i + 1, "value": original})
        
        # Check Duplicates (case-insensitive)
        lower = stripped.lower()
        if not lower: continue # Skip empty
        
        if lower in seen:
            duplicates.append({"index": i + 1, "value": stripped})
        else:
            seen.add(lower)
            
    return {
        "duplicates": duplicates,
        "whitespace_issues": whitespace_issues,
        "total_items": len(req.items),
        "valid": len(duplicates) == 0 and len(whitespace_issues) == 0
    }

@app.get("/api/history/unique_companies")
def get_unique_companies(request: Request):
    """Get all unique company links present in the dismissal history."""
    user_id = get_user_id(request)
    return db.get_unique_company_links(user_id=user_id)

@app.get("/api/history/export")
def export_history(request: Request):
    import io
    import csv
    from fastapi.responses import StreamingResponse
    
    user_id = get_user_id(request)
    # Fetch all history for export (not paginated)
    data = db.get_history(limit=10000, offset=0, user_id=user_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Job ID", "Title", "Company", "Location", "Reason", "Dismissed At", "Listed At", "Link"])
    
    for row in data:
        writer.writerow([
            row.get('job_id'),
            row.get('title'),
            row.get('company'),
            row.get('location'),
            row.get('reason'),
            row.get('dismissed_at'),
            row.get('listed_at'),
            f"https://www.linkedin.com/jobs/view/{row.get('job_id')}"
        ])
    
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=history_export_{datetime.now(timezone(timedelta(hours=-5))).strftime('%Y%m%d')}.csv"}
    )

@app.get("/api/geo_cache")
def get_geo_cache():
    return db.get_all_geo_cache()

@app.get("/api/geo_candidates/{master_id}")
def get_geo_candidates(master_id: str):
    return db.get_geo_candidates(master_id)


@app.post("/api/geo_cache/override")
def override_geo_cache(req: OverrideRequest):
    try:
        db.update_geo_cache_override(req.query, req.pp_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/geo_candidates")
def get_all_geo_candidates():
    return db.get_all_geo_candidates()

@app.post("/api/geo_candidate/update")
def update_geo_candidate(update: CandidateUpdate):
    try:
        db.update_geo_candidate(update.pp_id, update.corrected_name)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/geo_candidate/{pp_id}")
def delete_geo_candidate(pp_id: int):
    try:
        db.delete_geo_candidate(pp_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/geo_candidates")
def delete_all_geo_candidates():
    try:
        db.delete_all_geo_candidates()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/geo_cache/{query}")
def delete_geo_cache_entry(query: str):
    try:
        db.delete_geo_cache_entry(query)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== SAVED SEARCHES ==========

@app.get("/api/searches")
def get_saved_searches(request: Request):
    """Get all saved searches for the current user."""
    user_id = get_user_id(request)
    searches = db.get_saved_searches(user_id)
    return {"searches": searches}

@app.post("/api/searches")
def create_saved_search(req: SavedSearchRequest, request: Request):
    """Create a new saved search."""
    user_id = get_user_id(request)
    params = {
        "keywords": req.keywords,
        "location": req.location,
        "time_range": req.time_range,
        "limit": req.limit,
        "easy_apply": req.easy_apply,
        "relevant": req.relevant,
        "workplace_type": req.workplace_type
    }
    result = db.save_search(user_id, req.name, params)
    if result:
        return {"status": "created", "search": result}
    raise HTTPException(status_code=500, detail="Failed to save search")

@app.delete("/api/searches/{search_id}")
def delete_search(search_id: str, request: Request):
    user_id = get_user_id(request)
    success = db.delete_saved_search(search_id, user_id)
    if success:
        return {"status": "deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete search")

@app.patch("/api/searches/{search_id}")
def update_search(search_id: str, updates: dict, request: Request):
    user_id = get_user_id(request)
    # Generic update for now, mainly for 'name'
    if db.update_saved_search(search_id, user_id, updates):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to update search")

# ========== SEARCH HISTORY ==========

@app.get("/api/search_history")
def get_search_history(request: Request, limit: int = 20, offset: int = 0):
    """Get paginated search history for the current user."""
    user_id = get_user_id(request)
    history, total = db.get_search_history(user_id, limit, offset)
    return {
        "items": history,
        "total": total,
        "limit": limit,
        "offset": offset
    }

# ========== SEARCH HISTORY DETAILS ==========

@app.get("/api/search_history/{history_id}/details")
def get_history_details(history_id: str, request: Request):
    """Get full details for a specific run including logs and parsed jobs."""
    user_id = get_user_id(request)
    
    # Verify owner (implicitly via DB methods using history_id)
    logs = db.get_search_logs(history_id)
    jobs = db.get_jobs_for_run(history_id)
    
    return {
        "logs": logs,
        "jobs": jobs
    }

@app.delete("/api/search_history/{history_id}")
def delete_history_entry(history_id: str, request: Request):
    """Delete a search history entry."""
    # owner check could be done here if needed
    if db.delete_search_history(history_id):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to delete history item")

# --- Serve Static Files ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")

def kill_process_on_port(port):
    """Find and kill any process listening on the specified port."""
    try:
        # Check for process using port (lsof -i :PORT -t returns PIDs)
        cmd = f"lsof -i :{port} -t"
        try:
            # subprocess.check_output raises CalledProcessError if return code != 0 (e.g. no process found)
            output = subprocess.check_output(cmd, shell=True).decode().strip()
        except subprocess.CalledProcessError:
            return # No process using this port
            
        if output:
            pids = output.split('\n')
            for pid in pids:
                if pid.strip():
                    print(f"⚠️ Port {port} is in use by PID {pid}. Killing it...")
                    try:
                        os.kill(int(pid), 9)
                        print(f"✅ Killed PID {pid}")
                    except ProcessLookupError:
                        pass # Process already gone
            
            # Wait for port to be released
            print(f"⏳ Waiting for port {port} to be released...")
            time.sleep(2)
            
            # Double check
            try:
                subprocess.check_output(cmd, shell=True)
                # If we get here, port is still in use
                print(f"⚠️ Port {port} still appears in use. Waiting another second...")
                time.sleep(1)
            except subprocess.CalledProcessError:
                print(f"✅ Port {port} is now free.")
                return

    except Exception as e:
        print(f"⚠️ Error checking/killing port {port}: {e}")

if __name__ == "__main__":
    kill_process_on_port(8000)
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
