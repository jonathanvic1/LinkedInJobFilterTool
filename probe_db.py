import os
from supabase import create_client
from dotenv import load_dotenv

def probe_schema():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    client = create_client(url, key)
    
    print("🔍 Probing blocklists table...")
    try:
        # Try to select one row to see what we get back
        res = client.table("blocklists").select("*").limit(1).execute()
        if res.data:
            print(f"✅ Columns found: {list(res.data[0].keys())}")
        else:
            print("⚠️ Table is empty, cannot determine columns via select *")
            
        # Try a direct SQL-like check if possible (via RPC or just checking error messages)
        print("\n🔍 Testing blocklist_type filter...")
        res = client.table("blocklists").select("item").eq("blocklist_type", "job_title").execute()
        print(f"✅ Filter success: Found {len(res.data)} items.")
        
    except Exception as e:
        print(f"❌ Error during probe: {e}")

if __name__ == "__main__":
    probe_schema()
