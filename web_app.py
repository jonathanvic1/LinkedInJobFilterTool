import sys
import os
import threading
import time
import json
import time
import json
import json
from database import db
import uvicorn
import subprocess
import signal
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

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

state = ScraperState()
log_lock = threading.Lock()

# Models
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
    
# --- Helper Functions ---

def log_message(msg: str):
    """Add a message to the global log buffer."""
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {msg}"
        state.logs.append(entry)
        # Keep last 1000 logs
        if len(state.logs) > 1000:
            state.logs.pop(0)
            
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

def run_scraper_thread(params: SearchParams):
    state.running = True
    state.stop_event.clear()
    state.scraped_jobs = []
    state.logs = [] # Clear logs on new run
    state.total_found = 0
    state.total_dismissed = 0
    
    log_message("🚀 Starting Scraper Background Thread...")
    
    # Read blocklists from Supabase
    try:
        block_titles = db.get_blocklist("job_title")
        block_companies = db.get_blocklist("company_linkedin")
    except Exception as e:
        log_message(f"⚠️ Error reading blocklists from Supabase: {e}")
        block_titles = []
        block_companies = []

    # Initialize Scraper
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
            workplace_type=params.workplace_type
        )
        state.scraper_instance = scraper
        
        # We need to intercept the scraper's prints.
        # Since LinkedInScraper prints directly, we'll swap stdout temporarily for this thread?
        # Thread-local stdout interception is hard in Python.
        # Instead, we will rely on the fact that we globally swapped stdout below
        # or we could rewrite the scraper to take a logger.
        # For this quick implementation, we will use the global interceptor.
        
        # Run processing
        # Note: process_jobs is a blocking call. We can't easily interrupt it unless we modify the class
        # to check a stop flag. But we can kill the thread/process? No, thread killing is bad.
        # We will let it run or rely on the limit.
        # Ideally, we'd modify LinkedInScraper to check an external flag, but let's stick to 'limit' for now.
        
        scraper.process_jobs()
            
    except Exception as e:
        log_message(f"❌ Scraper crashed: {e}")
    finally:
        if state.scraper_instance:
            state.scraper_instance.close_session()
        state.running = False
        log_message("🛑 Scraper finished.")

# Redirect stdout globally (Affects entire process)
sys.stdout = LogInterceptor()

# --- API Endpoints ---

@app.post("/api/start")
def start_scraper(params: SearchParams):
    if state.running:
        raise HTTPException(status_code=400, detail="Scraper is already running")
    
    thread = threading.Thread(target=run_scraper_thread, args=(params,))
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
def get_blocklist(filename: str):
    name = "job_title" if filename == "blocklist.txt" else "company_linkedin"
    items = db.get_blocklist(name)
    return {"content": "\n".join(items)}

@app.post("/api/blocklist")
def save_blocklist(update: BlocklistUpdate):
    name = "job_title" if update.filename == "blocklist.txt" else "company_linkedin"
    items = update.content.split("\n")
    try:
        db.update_blocklist(name, items)
        return {"status": "saved"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/history")
def get_history(limit: int = 50, offset: int = 0):
    data = db.get_history(limit, offset)
    total = db.get_history_count()
    return {
        "items": data,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/api/geo_cache")
def get_geo_cache():
    return db.get_all_geo_cache()

@app.get("/api/geo_candidates/{master_id}")
def get_geo_candidates(master_id: str):
    return db.get_geo_candidates(master_id)

class OverrideRequest(BaseModel):
    query: str
    pp_id: str
    pp_name: str

@app.post("/api/geo_cache/override")
def override_geo_cache(req: OverrideRequest):
    try:
        db.update_geo_cache_override(req.query, req.pp_id, req.pp_name)
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
