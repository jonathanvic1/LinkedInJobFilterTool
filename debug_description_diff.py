import os
import sys
import difflib
from dotenv import load_dotenv
from database import db
from linkedin_scraper import LinkedInScraper

# Load environment variables robustly
try:
    with open(".env", "r") as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=", 1)
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                os.environ[key] = val
except Exception as e:
    print(f"⚠️ Error reading .env manually: {e}")

def compare_jobs(job_id1, job_id2):
    # Initialize DB and fetch session using manual env vars
    user_id = "5605d336-3914-460d-8517-573e0474668b"
    settings = db.get_user_settings(user_id)
    cookie_str = settings.get('linkedin_cookie') if settings else os.environ.get("LINKEDIN_COOKIES")
    
    if cookie_str and cookie_str.startswith('"') and cookie_str.endswith('"'):
        cookie_str = cookie_str[1:-1]

    scraper = LinkedInScraper(
        keywords="",
        location="",
        cookie_string=cookie_str,
        user_id=user_id
    )
    
    try:
        print(f"🔍 Fetching descriptions for {job_id1} and {job_id2}...")
        desc1 = scraper.fetch_job_description(job_id1)
        desc2 = scraper.fetch_job_description(job_id2)
        
        if not desc1 or not desc2:
            print("❌ Error: One or both descriptions could not be fetched.")
            return

        print("\n" + "="*50)
        print(f"📊 Comparison Results (Similarity Score)")
        print("="*50)
        
        s = difflib.SequenceMatcher(None, desc1, desc2)
        ratio = s.ratio()
        print(f"Similarity Score: {ratio:.4f} ({ratio*100:.2f}%)")
        
        print("\n" + "="*50)
        print(f"📝 Diff Analysis (Job {job_id1} -> Job {job_id2})")
        print("="*50)
        
        # Simple word-level diff
        diff = difflib.ndiff(desc1.splitlines(), desc2.splitlines())
        
        has_diff = False
        for line in diff:
            if line.startswith('+ ') or line.startswith('- '):
                print(line)
                has_diff = True
        
        if not has_diff:
            print("✅ No differences found in content (lines match exactly).")
            
    finally:
        scraper.close_session()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 debug_description_diff.py <job_id1> <job_id2>")
        sys.exit(1)
    
    j1 = sys.argv[1]
    j2 = sys.argv[2]
    compare_jobs(j1, j2)
