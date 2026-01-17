import os
from supabase import create_client

SUPABASE_URL = "https://ofjaluzetbgwpeboxecm.supabase.co"
SUPABASE_KEY = "sb_publishable_1z4CecOx5CQDVXaxVKFIKQ_MZpBOy0j"

def test_supabase():
    print(f"Connecting to {SUPABASE_URL}...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Check Count
    try:
        res = supabase.table("dismissed_jobs").select("*", count="exact", head=True).execute()
        print(f"Current Row Count: {res.count}")
    except Exception as e:
        print(f"❌ Error counting rows: {e}")

    # 2. Try Insertion
    test_id = "test_debug_001"
    try:
        data = {
            "job_id": test_id,
            "title": "Debug Job",
            "company": "Debug Co",
            "location": "Localhost",
            "dismiss_reason": "Testing",
            "job_url": "http://example.com"
        }
        res = supabase.table("dismissed_jobs").upsert(data).execute()
        print(f"Insertion Result: {res}")
    except Exception as e:
        print(f"❌ Error inserting row: {e}")

    # 3. Check Count Again
    try:
        res = supabase.table("dismissed_jobs").select("*", count="exact", head=True).execute()
        print(f"New Row Count: {res.count}")
    except Exception as e:
        print(f"❌ Error counting rows: {e}")

    # 4. Inspect a migrated row (not the test one)
    try:
        # Fetch a row that is NOT the test one
        res = supabase.table("dismissed_jobs").select("*").neq("job_id", test_id).limit(1).execute()
        if res.data:
            print(f"\n🔍 Sample Migrated Row: {res.data[0]}")
        else:
            print("\n❌ No migrated rows found (only test rows?)")
    except Exception as e:
        print(f"❌ Error fetching sample: {e}")

if __name__ == "__main__":
    test_supabase()
