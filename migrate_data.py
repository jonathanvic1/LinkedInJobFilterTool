import sqlite3
import os
from supabase import create_client
from tqdm import tqdm
import math

# Configuration provided by user earlier
# Note: In a production script we wouldn't hardcode, but for this one-off local migration it's expedient
SUPABASE_URL = "https://ofjaluzetbgwpeboxecm.supabase.co"
SUPABASE_KEY = "sb_publishable_1z4CecOx5CQDVXaxVKFIKQ_MZpBOy0j"

def migrate_dismissed_jobs(cursor, supabase):
    print("🚀 Migrating 'dismissed_jobs'...")
    cursor.execute("SELECT * FROM dismissed_jobs")
    # Fetch all rows
    rows = cursor.fetchall()
    # Get column names
    col_names = [description[0] for description in cursor.description]
    
    total = len(rows)
    print(f"   Found {total} rows.")
    
    if total == 0:
        return

    # Supabase allows batch upsert. Let's do batches of 1000.
    batch_size = 1000
    
    for i in tqdm(range(0, total, batch_size), desc="Uploading Batches"):
        batch = rows[i:i + batch_size]
        data_payload = []
        for row in batch:
            row_dict = dict(zip(col_names, row))
            # Clean up boolean fields (0/1 to True/False for Postgres if needed, though Supabase handles it largely)
            if 'is_reposted' in row_dict:
                row_dict['is_reposted'] = bool(row_dict['is_reposted'])
            
            # Ensure proper types
            data_payload.append(row_dict)
            
        try:
            supabase.table("dismissed_jobs").upsert(data_payload).execute()
        except Exception as e:
            print(f"❌ Error migrating batch {i}: {e}")

def migrate_geo_cache(cursor, supabase):
    print("\n🚀 Migrating 'geo_cache'...")
    cursor.execute("SELECT * FROM geo_cache")
    rows = cursor.fetchall()
    col_names = [description[0] for description in cursor.description]
    
    print(f"   Found {len(rows)} rows.")
    if not rows: return

    data_payload = []
    for row in rows:
        row_dict = dict(zip(col_names, row))
        data_payload.append(row_dict)
    
    try:
        supabase.table("geo_cache").upsert(data_payload).execute()
        print("   ✅ Geo Cache migrated.")
    except Exception as e:
        print(f"   ❌ Error migrating geo_cache: {e}")

def migrate_geo_candidates(cursor, supabase):
    print("\n🚀 Migrating 'geo_candidates'...")
    cursor.execute("SELECT * FROM geo_candidates")
    rows = cursor.fetchall()
    col_names = [description[0] for description in cursor.description]
    
    print(f"   Found {len(rows)} rows.")
    if not rows: return
    
    batch_size = 1000
    total = len(rows)
    
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        data_payload = []
        for row in batch:
            row_dict = dict(zip(col_names, row))
            data_payload.append(row_dict)
        try:
            supabase.table("geo_candidates").upsert(data_payload).execute()
        except Exception as e:
            print(f"   ❌ Error migrating batch {i}: {e}")
    print("   ✅ Geo Candidates migrated.")

def main():
    if not os.path.exists("dismissed_jobs.db"):
        print("❌ dismiss_jobs.db not found!")
        return

    # Connect SQLite
    conn = sqlite3.connect("dismissed_jobs.db")
    cursor = conn.cursor()

    # Connect Supabase
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return

    try:
        migrate_dismissed_jobs(cursor, supabase)
        migrate_geo_cache(cursor, supabase)
        migrate_geo_candidates(cursor, supabase)
        print("\n🎉 Migration Complete!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
