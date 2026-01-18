import psycopg2
import os

db_url = os.environ.get("SUPABASE_DB_URL")
if not db_url:
    print("❌ SUPABASE_DB_URL not found")
    exit(1)

sql = """
-- Migrate geo_cache columns to bigint
ALTER TABLE geo_cache 
ALTER COLUMN master_geo_id TYPE bigint USING master_geo_id::bigint,
ALTER COLUMN populated_place_id TYPE bigint USING populated_place_id::bigint;

-- Migrate geo_candidates columns
-- Convert master_geo_id from text (csv) to bigint array
ALTER TABLE geo_candidates 
ALTER COLUMN pp_id TYPE bigint USING pp_id::bigint,
ALTER COLUMN master_geo_id TYPE bigint[] USING string_to_array(master_geo_id, ',')::bigint[];
"""

try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    print("✅ Migration successful")
except Exception as e:
    print(f"❌ Migration failed: {e}")
finally:
    if 'conn' in locals():
        conn.close()
