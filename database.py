import os
import time
import random
import threading
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

class Database:
    _instance = None
    _lock = threading.Lock()  # Thread lock for write operations
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._local = threading.local()
            cls._instance._init_config()
            cls._instance._dup_cache = {}  # Cache for get_earliest_duplicate
            cls._instance._dup_cache_lock = threading.Lock()
        return cls._instance
    
    def _init_config(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if not self.url or not self.key:
            print("⚠️ SUPABASE_URL or SUPABASE_KEY not found in environment variables. DB operations will fail.")

    @property
    def client(self) -> Client:
        """Get or initialize a thread-local Supabase client."""
        if not hasattr(self._local, "client"):
            if not self.url or not self.key:
                self._local.client = None
            else:
                try:
                    # Initialize client for this thread
                    self._local.client = create_client(self.url, self.key)
                    # print(f"✅ Supabase client initialized for thread {threading.get_ident()}")
                except Exception as e:
                    print(f"❌ Failed to initialize Supabase client for thread {threading.get_ident()}: {e}")
                    self._local.client = None
        return self._local.client

    def _retry_request(self, func, *args, max_retries=3, initial_delay=0.5, **kwargs):
        """Generic retry wrapper with exponential backoff and jitter."""
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                err_msg = str(e).lower()
                # Check for transient errors or Cloudflare/Supabase connection limits
                is_transient = any(kw in err_msg for kw in ["terminated", "timeout", "connection", "502", "503", "504", "429", "batch"])
                
                if i < max_retries - 1 and is_transient:
                    delay = initial_delay * (2 ** i) + random.uniform(0, 0.1)
                    print(f"   ⚠️ DB Request failed (try {i+1}/{max_retries}): {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    raise e
        return None

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
        
        def _execute():
            query = self.client.table("dismissed_jobs").select("job_id").in_("job_id", job_ids)
            if user_id:
                query = query.eq("user_id", user_id)
            return query.execute()

        try:
            response = self._retry_request(_execute)
            if response and response.data:
                return {row['job_id'] for row in response.data}
        except Exception as e:
            print(f"   ⚠️ DB Error (get_dismissed_job_ids): {e}")
        return set()

    def save_dismissed_job(self, job_id, title, company, location, reason, job_url, company_url, is_reposted=False, listed_at=None, user_id=None, history_id=None):
        if not self.client: return
        data = {
            'job_id': job_id,
            'title': title,
            'company': company,
            'location': location,
            'dismiss_reason': reason, # Use the passed reason
            'company_linkedin': company_url,
            'is_reposted': is_reposted,
            'listed_at': listed_at,
            'dismissed_at': datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat()
        }
        if user_id:
            data["user_id"] = user_id
        if history_id:
            data["history_id"] = history_id
            
        def _execute():
            return self.client.table("dismissed_jobs").upsert(data).execute()

        try:
            with self._lock:  # Thread-safe write
                self._retry_request(_execute)
            print(f"   💾 Saved to Supabase: {title}")
        except Exception as e:
            print(f"   ⚠️ DB Error (save_dismissed_job): {e}")

    def batch_save_dismissed_jobs(self, jobs_data, history_id=None, silent=False):
        """Save multiple dismissed jobs to Supabase history, only if they don't exist yet."""
        if not self.client or not jobs_data: return
        
        # 1. Clean data and collect IDs
        clean_data_map = {}
        for j in jobs_data:
            if j and j.get('job_id'):
                if history_id:
                    j['history_id'] = history_id
                clean_data_map[j['job_id']] = j
        
        if not clean_data_map:
            return

        # 2. Check which IDs already exist in Supabase to avoid redundant writes
        all_ids = list(clean_data_map.keys())
        existing_ids = set()
        try:
            # Check in chunks of 100 to avoid URL length issues
            for i in range(0, len(all_ids), 100):
                chunk = all_ids[i:i+100]
                response = self.client.table("dismissed_jobs").select("job_id").in_("job_id", chunk).execute()
                if response.data:
                    for r in response.data:
                        existing_ids.add(r['job_id'])
        except Exception as e:
            if not silent:
                print(f"   ⚠️ DB Error (pre-save check): {e}")

        # 3. Filter out existing jobs
        new_jobs = [j for jid, j in clean_data_map.items() if jid not in existing_ids]
        
        if not new_jobs:
            if not silent:
                print("   ✨ All jobs already recorded in Supabase. Skipping batch save.")
            return
            
        if not silent:
            print(f"   💾 Saving {len(new_jobs)} new jobs to Supabase history (skipped {len(existing_ids)} duplicates)...")
        
        success_count = 0
        for job in new_jobs:
            title = job.get('title', 'Unknown Title')
            job_id = job.get('job_id')
            
            def _execute():
                return self.client.table("dismissed_jobs").upsert(job).execute()

            try:
                with self._lock:
                    self._retry_request(_execute)
                if not silent:
                    print(f"      ✅ Saved: {title} (ID: {job_id})")
                success_count += 1
            except Exception as e:
                if not silent:
                    print(f"      ❌ Failed to save {title}: {e}")
        
        if not silent:
            if success_count == len(new_jobs):
                print(f"   ✨ All {len(new_jobs)} new jobs successfully recorded.")
            else:
                print(f"   📊 Saved {success_count}/{len(new_jobs)} new jobs.")

    def get_unique_company_links(self, user_id=None):
        """Fetch all unique company URLs from the dismissal history by paging through all records."""
        if not self.client: return []
        try:
            all_links = set()
            offset = 0
            page_size = 1000
            
            while True:
                query = self.client.table("dismissed_jobs").select("company_linkedin").range(offset, offset + page_size - 1)
                if user_id:
                    query = query.eq("user_id", user_id)
                
                response = query.execute()
                if not response.data:
                    break
                
                for row in response.data:
                    if row.get('company_linkedin'):
                        all_links.add(row['company_linkedin'])
                
                if len(response.data) < page_size:
                    break
                
                offset += page_size
                
            return list(all_links)
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
        
        def _execute():
            return self.client.table("geo_cache").select("*").eq("location_query", query.strip().title()).execute()

        try:
            response = self._retry_request(_execute)
            if response and response.data:
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
        
        # 1. Check local cache first
        cache_key = (title.lower().strip(), company.lower().strip() if company else "")
        with self._dup_cache_lock:
            if cache_key in self._dup_cache:
                return self._dup_cache[cache_key]

        def _execute():
            return self.client.table("dismissed_jobs")\
                .select("job_id")\
                .eq("title", title)\
                .eq("company", company)\
                .order("listed_at", desc=False)\
                .limit(1)\
                .execute()
        
        try:
            response = self._retry_request(_execute)
            
            job_id = None
            if response and response.data:
                job_id = response.data[0]['job_id']
            
            # 2. Update cache
            with self._dup_cache_lock:
                self._dup_cache[cache_key] = job_id
            return job_id
            
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
        
        def _execute():
            query = self.client.table("blocklists").select("item").eq("blocklist_type", name)
            if user_id:
                query = query.eq("user_id", user_id)
            return query.execute()

        try:
            res = self._retry_request(_execute)
            if res and res.data:
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
            return []

    def get_user_settings(self, user_id):
        """Fetch user settings including LinkedIn cookie."""
        if not self.client or not user_id: return None
        
        def _execute():
            return self.client.table("user_settings").select("*").eq("user_id", user_id).execute()

        try:
            response = self._retry_request(_execute)
            if response and response.data:
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
                "updated_at": datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat()
            }
            self.client.table("user_settings").upsert(data).execute()
            return True
        except Exception as e:
            print(f"   ⚠️ DB Error (save_user_settings): {e}")
            return False

    # ========== SAVED SEARCHES ==========
    
    def get_saved_searches(self, user_id):
        """Get all saved searches for a user."""
        if not self.client or not user_id: return []
        try:
            response = self.client.table("saved_searches").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"   ⚠️ DB Error (get_saved_searches): {e}")
            return []
    
    def save_search(self, user_id, name, params):
        """Create or update a saved search."""
        if not self.client or not user_id: return None
        try:
            data = {
                "user_id": user_id,
                "name": name,
                "keywords": params.get("keywords", ""),
                "location": params.get("location", "Canada"),
                "time_range": params.get("time_range", "all"),
                "job_limit": params.get("limit", 25),
                "easy_apply": params.get("easy_apply", False),
                "relevant": params.get("relevant", False),
                "workplace_type": params.get("workplace_type", []),
                "updated_at": datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat()
            }
            response = self.client.table("saved_searches").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"   ⚠️ DB Error (save_search): {e}")
            return None
    
    def delete_saved_search(self, search_id, user_id):
        """Delete a saved search."""
        if not self.client or not user_id: return False
        try:
            self.client.table("saved_searches").delete().eq("id", search_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"   ⚠️ DB Error (delete_saved_search): {e}")
            return False

    def update_saved_search(self, search_id, user_id, updates):
        """Update a saved search configuration (e.g., renaming)."""
        if not self.client: return False
        try:
            # Ensure updated_at is refreshed
            updates['updated_at'] = datetime.now(timezone.utc).isoformat()
            self.client.table("saved_searches").update(updates).eq("id", search_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"   ⚠️ DB Error (update_saved_search): {e}")
            return False
    
    # ========== SEARCH HISTORY ==========
    
    def log_search_start(self, user_id, params):
        """Log the start of a search run. Returns the history ID."""
        if not self.client or not user_id: return None
        try:
            data = {
                "user_id": user_id,
                "keywords": params.get("keywords") or "",
                "location": params.get("location") or "",
                "time_range": params.get("time_range", "all"),
                "status": "running",
                "started_at": datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat()
            }
            response = self.client.table("search_history").insert(data).execute()
            return response.data[0]["id"] if response.data else None
        except Exception as e:
            print(f"   ⚠️ DB Error (log_search_start): {e}")
            return None
    
    def log_search_complete(self, history_id, total_found, total_dismissed, total_skipped, status="completed"):
        """Update a search history entry with final stats."""
        if not self.client or not history_id: return False
        try:
            data = {
                "total_found": total_found,
                "total_dismissed": total_dismissed,
                "total_skipped": total_skipped,
                "status": status,
                "completed_at": datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat()
            }
            self.client.table("search_history").update(data).eq("id", history_id).execute()
            
            # Add final log message
            final_msg = f"Search {status}. Found: {total_found}, Dismissed: {total_dismissed}, Skipped: {total_skipped}"
            self.log_search_event(history_id, final_msg, level='info')
            return True
        except Exception as e:
            print(f"   ⚠️ DB Error (log_search_complete): {e}")
            return False

    def log_search_event(self, history_id, message, level='info'):
        """Log a persistent event for a search run."""
        if not self.client or not history_id: return
        try:
            data = {
                "history_id": history_id,
                "message": message,
                "level": level,
                "created_at": datetime.now(timezone(timedelta(hours=-5))).strftime('%Y-%m-%d %H:%M:%S')
            }
            self.client.table("search_logs").insert(data).execute()
        except Exception as e:
            print(f"   ⚠️ DB Error (log_search_event): {e}")

    def get_search_logs(self, history_id):
        """Fetch all logs for a specific run."""
        if not self.client or not history_id: return []
        try:
            response = self.client.table("search_logs").select("*").eq("history_id", history_id).order("created_at", desc=False).execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"   ⚠️ DB Error (get_search_logs): {e}")
            return []

    def get_jobs_for_run(self, history_id):
        """Get all dismissed jobs processed during a specific run."""
        if not self.client or not history_id: return []
        try:
            response = self.client.table("dismissed_jobs").select("*").eq("history_id", history_id).order("dismissed_at", desc=True).execute()
            # Map back to API format
            jobs = []
            for row in response.data:
                jobs.append({
                    "job_id": row.get('job_id'),
                    "title": row.get('title'),
                    "company": row.get('company'),
                    "location": row.get('location'),
                    "reason": row.get('dismiss_reason'),
                    "dismissed_at": row.get('dismissed_at')
                })
            return jobs
        except Exception as e:
            print(f"   ⚠️ DB Error (get_jobs_for_run): {e}")
            return []
    
    def get_search_history(self, user_id, limit=20, offset=0):
        """Get paginated search history for a user."""
        if not self.client or not user_id: return [], 0
        try:
            # Get total count
            count_response = self.client.table("search_history").select("id", count="exact").eq("user_id", user_id).execute()
            total = count_response.count if count_response.count else 0
            
            # Get paginated data
            response = self.client.table("search_history").select("*").eq("user_id", user_id).order("started_at", desc=True).range(offset, offset + limit - 1).execute()
            return response.data if response.data else [], total
        except Exception as e:
            print(f"   ⚠️ DB Error (get_search_history): {e}")
            return [], 0
    def delete_search_history(self, history_id):
        """Delete a search history entry and all associated logs."""
        if not self.client or not history_id: return False
        try:
            self.client.table("search_history").delete().eq("id", history_id).execute()
            return True
        except Exception as e:
            print(f"   ⚠️ DB Error (delete_search_history): {e}")
            return False

db = Database()
