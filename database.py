import os
import threading
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

class Database:
    _instance = None
    _lock = threading.Lock()  # Thread lock for write operations
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance
    
    def _init_client(self):
        url = os.environ.get("SUPABASE_URL")
        # Prioritize Service Role Key for backend to bypass RLS
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            print("⚠️ SUPABASE_URL or SUPABASE_KEY not found in environment variables. DB operations will fail.")
            self.client = None
        else:
            try:
                self.client: Client = create_client(url, key)
                is_service = "SUPABASE_SERVICE_ROLE_KEY" in os.environ
                print(f"✅ Supabase client initialized ({'Service Role' if is_service else 'Anon/Standard Key'})")
            except Exception as e:
                print(f"❌ Failed to initialize Supabase: {e}")
                self.client = None

    def is_job_dismissed(self, job_id, user_id=None):
        if not self.client: return False
        try:
            query = self.client.table("dismissed_jobs").select("job_id").eq("job_id", job_id)
            if user_id:
                query = query.eq("user_id", user_id)
            response = query.execute()
            return len(response.data) > 0
        except Exception as e:
            print(f"⚠️ DB Error (is_job_dismissed): {e}")
            return False
            
    def get_dismissed_job_ids(self, job_ids, user_id=None):
        """Batch check if jobs are dismissed."""
        if not self.client or not job_ids: return set()
        try:
            # PostgREST in_ expects parens or strict formatting, but Supabase-py handles list directly often.
            # However, for safety, let's pass list directly.
            query = self.client.table("dismissed_jobs").select("job_id").in_("job_id", job_ids)
            if user_id:
                query = query.eq("user_id", user_id)
            response = query.execute()
            return {row['job_id'] for row in response.data}
        except Exception as e:
            print(f"⚠️ DB Error (get_dismissed_job_ids): {e}")
            return set()

    def save_dismissed_job(self, job_id, title, company, location, reason, job_url, company_url, is_reposted=False, listed_at=None, user_id=None):
        if not self.client: return
        data = {
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "dismiss_reason": reason,
            "company_linkedin": company_url,
            "is_reposted": is_reposted,
            "listed_at": listed_at,
            "dismissed_at": datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat(),
        }
        if user_id:
            data["user_id"] = user_id
        try:
            with self._lock:  # Thread-safe write
                self.client.table("dismissed_jobs").upsert(data).execute()
            print(f"   💾 Saved to Supabase: {title}")
        except Exception as e:
            print(f"   ⚠️ DB Error (save_dismissed_job): {e}")

    def batch_save_dismissed_jobs(self, jobs_data):
        """Batch upsert multiple dismissed jobs at once."""
        if not self.client or not jobs_data: return
        
        # Filter out None values and clean data
        clean_data = [j for j in jobs_data if j and j.get('job_id')]
        if not clean_data:
            return
            
        try:
            self.client.table("dismissed_jobs").upsert(clean_data).execute()
            print(f"   ✅ Batch saved {len(clean_data)} jobs to Supabase")
        except Exception as e:
            print(f"   ⚠️ DB Error (batch_save_dismissed_jobs): {e}")
            # Fallback: try individual saves
            print("   🔄 Falling back to individual saves...")
            for job in clean_data:
                try:
                    with self._lock:
                        self.client.table("dismissed_jobs").upsert(job).execute()
                except Exception as e2:
                    print(f"      ⚠️ Failed to save {job.get('title')}: {e2}")

    def get_unique_company_links(self, user_id=None):
        """Fetch all unique company URLs from the dismissal history."""
        if not self.client: return []
        try:
            # We fetch everything and deduplicate in Python for simplicity
            query = self.client.table("dismissed_jobs").select("company_linkedin").limit(10000)
            if user_id:
                query = query.eq("user_id", user_id)
            
            response = query.execute()
            links = {row['company_linkedin'] for row in response.data if row.get('company_linkedin')}
            return list(links)
        except Exception as e:
            print(f"   ⚠️ DB Error (get_unique_company_links): {e}")
            return []

    def delete_dismissed_job(self, job_id):
        if not self.client: return False
        try:
            self.client.table("dismissed_jobs").delete().eq("job_id", job_id).execute()
            print(f"   🗑️  Removed from Supabase: Job ID {job_id}")
            return True
        except Exception as e:
            print(f"   ⚠️ DB Error (delete_dismissed_job): {e}")
            return False

    def get_geo_cache(self, query):
        if not self.client: return None
        try:
            response = self.client.table("geo_cache").select("*").eq("location_query", query.strip().title()).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print(f"   ⚠️ DB Error (get_geo_cache): {e}")
        return None

    def save_geo_cache(self, location_query, master_geo_id, populated_place_id):
        if not self.client: return
        # Self-healing: if pp_id matches master_id, it's a regional query, not a city-level one
        master_id_int = int(master_geo_id) if master_geo_id else None
        pp_id_int = int(populated_place_id) if populated_place_id else None
        if pp_id_int and master_id_int and pp_id_int == master_id_int:
            pp_id_int = None

        data = {
            "location_query": location_query.strip().title(),
            "master_geo_id": master_id_int,
            "populated_place_id": pp_id_int,
            # updated_at defaults to NOW()
        }
        try:
            self.client.table("geo_cache").upsert(data).execute()
        except Exception as e:
            print(f"   ⚠️ DB Error (save_geo_cache): {e}")

    def update_geo_cache_override(self, location_query, populated_place_id):
         if not self.client: return
         try:
             # Self-healing: Fetch master_id to compare
             existing = self.client.table("geo_cache").select("master_geo_id").eq("location_query", location_query.strip().title()).execute()
             if existing.data:
                 master_id = existing.data[0].get('master_geo_id')
                 if master_id and int(populated_place_id) == int(master_id):
                     populated_place_id = None

             self.client.table("geo_cache").update({
                 "populated_place_id": int(populated_place_id) if populated_place_id else None,
                 "updated_at": "now()"
             }).eq("location_query", location_query.strip().title()).execute()
         except Exception as e:
             raise e

    def get_geo_candidates(self, master_geo_id):
        if not self.client: return []
        try:
            # master_geo_id is now a bigint[] column, so we use contains logic
            # PostgREST expects an array literal or list for .contains()
            response = self.client.table("geo_candidates")\
                .select("*")\
                .contains("master_geo_id", [str(master_geo_id)])\
                .execute()
            return [{"id": r['pp_id'], "name": r['pp_name'], "corrected_name": r.get('pp_corrected_name')} for r in response.data]
        except Exception as e:
            print(f"   ⚠️ DB Error (get_geo_candidates): {e}")
            return []

    def get_all_geo_candidates(self):
        if not self.client: return []
        try:
            response = self.client.table("geo_candidates").select("*").order("master_geo_id").order("pp_name").execute()
            return response.data
        except Exception as e:
            print(f"   ⚠️ DB Error (get_all_geo_candidates): {e}")
            return []

    def update_geo_candidate(self, pp_id, corrected_name):
        if not self.client: return
        try:
            self.client.table("geo_candidates").update({"pp_corrected_name": corrected_name}).eq("pp_id", pp_id).execute()
        except Exception as e:
            raise e

    def delete_geo_candidate(self, pp_id):
        if not self.client: return
        try:
            self.client.table("geo_candidates").delete().eq("pp_id", pp_id).execute()
        except Exception as e:
            raise e

    def delete_all_geo_candidates(self):
        if not self.client: return
        try:
            # Delete all rows where pp_id is not null (effective clear)
            self.client.table("geo_candidates").delete().neq("pp_id", 0).execute()
        except Exception as e:
            raise e

    def save_geo_candidates(self, master_geo_id, candidates):
        if not self.client: return
        
        try:
            # 1. Fetch existing candidates for these pp_ids
            # PostgREST serialization requires string lists for .in_ filters
            pp_ids = [str(c['id']) for c in candidates]
            response = self.client.table("geo_candidates").select("pp_id, master_geo_id").in_("pp_id", pp_ids).execute()
            existing_map = {row['pp_id']: row['master_geo_id'] for row in response.data} if response.data else {}

            rows = []
            for c in candidates:
                pp_id = int(c['id'])
                existing_masters = existing_map.get(pp_id, [])
                
                # Merge master_geo_ids as a list of integers
                master_set = set(existing_masters) if existing_masters else set()
                master_set.add(int(master_geo_id))
                consolidated_masters = sorted(list(master_set))

                rows.append({
                    "master_geo_id": consolidated_masters, # Persisted as bigint[]
                    "pp_id": pp_id,
                    "pp_name": c['name'],
                    "pp_corrected_name": c.get('corrected_name') or c['name']
                })
            
            if rows:
                self.client.table("geo_candidates").upsert(rows, on_conflict="pp_id").execute()
                
        except Exception as e:
            print(f"   ⚠️ DB Error (save_geo_candidates): {e}")
                
    def get_candidate_by_corrected_name(self, name):
        if not self.client: return None
        try:
            # Smart case matching: try exact title case first, then case-insensitive
            query = name.strip()
            response = self.client.table("geo_candidates")\
                .select("pp_id, master_geo_id")\
                .ilike("pp_corrected_name", query)\
                .limit(1)\
                .execute()
            
            if response.data:
                data = response.data[0]
                master_ids = data.get('master_geo_id', [])
                # Take first ID if it's an array
                data['master_geo_id'] = master_ids[0] if master_ids else None
                return data
            return None
        except Exception as e:
            print(f"   ⚠️ DB Error (get_candidate_by_corrected_name): {e}")
            return None

    def get_earliest_duplicate(self, title, company):
        if not self.client: return None
        try:
            # Supabase Python client currently doesn't support complex ordering in a simple way as robustly as SQL
            # But .order('listed_at', desc=False) works
            response = self.client.table("dismissed_jobs")\
                .select("job_id")\
                .eq("title", title)\
                .eq("company", company)\
                .order("listed_at", desc=False)\
                .limit(1)\
                .execute()
            
            if response.data:
                return response.data[0]['job_id']
        except Exception as e:
             print(f"   ⚠️ DB Error (get_earliest_duplicate): {e}")
        return None

    def get_jobs_by_title_company(self, title_pattern, company_pattern):
        if not self.client: return []
        try:
            response = self.client.table("dismissed_jobs")\
                .select("job_id, title, company")\
                .ilike("title", title_pattern)\
                .ilike("company", company_pattern)\
                .execute()
            return response.data
        except Exception as e:
            print(f"⚠️ DB Error (get_jobs_by_title_company): {e}")
            return []

    def get_history(self, limit=50, offset=0, user_id=None):
        if not self.client: return []
        try:
            query = self.client.table("dismissed_jobs").select("*")
            if user_id:
                query = query.eq("user_id", user_id)
            response = query\
                .order("dismissed_at", desc=True)\
                .range(offset, offset + limit - 1)\
                .execute()
            
            # Map back to API format
            history = []
            for row in response.data:
                history.append({
                    "job_id": row.get('job_id'),
                    "title": row.get('title'),
                    "company": row.get('company'),
                    "location": row.get('location'),
                    "reason": row.get('dismiss_reason'),
                    "dismissed_at": row.get('dismissed_at'),
                    "listed_at": row.get('listed_at')
                })
            return history
        except Exception as e:
            print(f"DB Error (history): {e}")
            return []

    def get_history_count(self, user_id=None):
        if not self.client: return 0
        try:
            query = self.client.table("dismissed_jobs").select("*", count="exact", head=True)
            if user_id:
                query = query.eq("user_id", user_id)
            response = query.execute()
            return response.count
        except Exception as e:
            print(f"DB Error (history count): {e}")
            return 0

    def get_all_geo_cache(self):
        if not self.client: return []
        try:
            response = self.client.table("geo_cache").select("*").order("location_query", desc=False).execute()
            # Load all candidates at once to avoid N+1 queries
            all_candidates = []
            try:
                cand_res = self.client.table("geo_candidates").select("*").execute()
                all_candidates = cand_res.data
            except Exception as e:
                print(f"   ⚠️ DB Warning (Load Candidates): {e}")
                pass

            cache = []
            for row in response.data:
                master_id = row.get('master_geo_id')
                pp_id = row.get('populated_place_id')
                
                # Count candidates for this master_id
                place_count = len([c for c in all_candidates if c.get('master_geo_id') == master_id])
                
                # Get specific names if refined
                pp_name = None
                pp_corrected_name = None
                if pp_id:
                    match = next((c for c in all_candidates if c.get('pp_id') == pp_id and c.get('master_geo_id') == master_id), None)
                    if match:
                        pp_name = match.get('pp_name')
                        pp_corrected_name = match.get('pp_corrected_name')

                cache.append({
                    "query": row.get('location_query', '').title(),
                    "master_id": master_id,
                    "pp_id": pp_id,
                    "pp_name": pp_name,
                    "pp_corrected_name": pp_corrected_name,
                    "place_count": place_count
                })
            return cache
        except Exception as e:
            return []
    
    def delete_geo_cache_entry(self, query):
        if not self.client: return
        try:
             self.client.table("geo_cache").delete().eq("location_query", query.strip().title()).execute()
        except Exception as e:
            raise e

    def get_blocklist(self, name, user_id=None):
        """Fetch blocklist items by name ('job_title' or 'company_linkedin')"""
        if not self.client: return []
        try:
            query = self.client.table("blocklists").select("item").eq("blocklist_type", name)
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()
            return [row['item'] for row in res.data]
        except Exception as e:
            print(f"⚠️ DB Error (get_blocklist {name}): {e}")
            return []

    def update_blocklist(self, name, items, user_id=None):
        """Replace the entire blocklist for a given name."""
        if not self.client: return
        try:
            # 1. Clear existing for this user
            query = self.client.table("blocklists").delete().eq("blocklist_type", name)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
            
            # 2. Insert new
            if items:
                rows = [{"blocklist_type": name, "item": item.strip(), "user_id": user_id} for item in items if item.strip()]
                if rows:
                    self.client.table("blocklists").insert(rows).execute()
        except Exception as e:
            print(f"⚠️ DB Error (update_blocklist {name}): {e}")

    def get_user_settings(self, user_id):
        """Fetch user settings including LinkedIn cookie."""
        if not self.client or not user_id: return None
        try:
            response = self.client.table("user_settings").select("*").eq("user_id", user_id).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print(f"⚠️ DB Error (get_user_settings): {e}")
        return None

    def save_user_settings(self, user_id, linkedin_cookie, page_delay=2.0, job_delay=1.0):
        """Save or update user settings."""
        if not self.client or not user_id: return False
        try:
            data = {
                "user_id": user_id,
                "linkedin_cookie": linkedin_cookie,
                "page_delay": page_delay,
                "job_delay": job_delay,
                "updated_at": "now()"
            }
            self.client.table("user_settings").upsert(data).execute()
            return True
        except Exception as e:
            print(f"   ⚠️ DB Error (save_user_settings): {e}")
            return False

db = Database()
