import os
from supabase import create_client

SUPABASE_URL = "https://ofjaluzetbgwpeboxecm.supabase.co"
SUPABASE_KEY = "sb_publishable_1z4CecOx5CQDVXaxVKFIKQ_MZpBOy0j"

def cleanup():
    print(f"Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    job_id = "test_debug_001"
    try:
        print(f"Deleting job {job_id}...")
        res = supabase.table("dismissed_jobs").delete().eq("job_id", job_id).execute()
        print(f"Result: {res}")
    except Exception as e:
        print(f"❌ Error deleting: {e}")

if __name__ == "__main__":
    cleanup()
