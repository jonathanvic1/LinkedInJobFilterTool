#!/usr/bin/env python3
"""
LinkedIn Job Scraper

A script to scrape job postings from LinkedIn based on various search criteria.
Uses curl_cffi with Chrome 136 impersonation and authenticated cookies to query the Voyager API.
"""

import os
import urllib.parse
import difflib
from tqdm import tqdm
from time import sleep
from typing import List
from database import db
from datetime import datetime, timezone, timedelta
from curl_cffi import requests

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

# URLs
VOYAGER_API_URL = 'https://www.linkedin.com/voyager/api/voyagerJobsDashJobCards'
JOB_DETAILS_URL = 'https://www.linkedin.com/voyager/api/jobs/jobPostings/'
DISMISS_URL = 'https://www.linkedin.com/voyager/api/voyagerJobsDashJobPostingRelevanceFeedback?action=dismiss'
UNDO_DISMISS_URL = 'https://www.linkedin.com/voyager/api/voyagerJobsDashJobPostingRelevanceFeedback?action=undoDismiss'

# Default Headers (will be augmented with auth headers)
HEADERS = {
    "accept": "application/vnd.linkedin.normalized+json+2.1",
    "accept-language": "en-US,en;q=0.9",
    "sec-ch-prefers-color-scheme": "dark",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-li-lang": "en_US",
    "x-restli-protocol-version": "2.0.0"
}

class LinkedInScraper:
    def __init__(self, 
                 keywords: str = '',
                 location: str = 'Canada',
                 limit_jobs: int = 0,
                 dismiss_keywords: List[str] = None,
                 dismiss_companies: List[str] = None,
                 relevant: bool = False,
                 time_filter: str = 'all',
                 easy_apply: bool = False,
                 workplace_type: List[int] = None,
                 user_id: str = None,
                 cookie_string: str = None,
                 page_delay: float = 2.0,
                 job_delay: float = 1.0):
        self.keywords = keywords
        self.location = location
        self.limit_jobs = limit_jobs
        self.easy_apply = easy_apply
        self.cookie_string = cookie_string
        self.page_delay = page_delay
        self.job_delay = job_delay
        self.dismiss_titles = [k.lower().strip() for k in dismiss_keywords if k and k.strip()] if dismiss_keywords else []
        
        # Sanitize company inputs (extract slug from URL if present)
        # e.g. "https://www.linkedin.com/company/micro1/" -> "micro1"
        self.dismiss_companies = []
        if dismiss_companies:
            for k in dismiss_companies:
                if k and k.strip():
                    cleaned = k.lower().strip()
                    # Extract slug if it's a URL
                    if 'linkedin.com/company/' in cleaned:
                        cleaned = cleaned.split('linkedin.com/company/')[-1].split('?')[0].strip('/')
                    self.dismiss_companies.append(cleaned)
        self.relevant = relevant
        self.time_filter = time_filter
        self.workplace_type = workplace_type if workplace_type else []
        self.user_id = user_id
        
        # Create logs directory if it doesn't exist - SKIPPED FOR VERCEL
        # os.makedirs('logs', exist_ok=True)
        
        # Initialize DB
        self.init_db()
        
        # Initialize curl_cffi session
        self.session = requests.Session()
        
        # Load Cookies
        self.load_cookies()
        
        # Update headers
        self.session.headers.update(HEADERS)
        if hasattr(self, 'csrf_token') and self.csrf_token:
            self.session.headers.update({'csrf-token': self.csrf_token})
        
        print("🔧 Initialized scraper with curl_cffi Chrome 136 impersonation and Authenticated Session")

    def load_cookies(self):
        """Load cookies from provided string, env var, or file."""
        cookie_str = self.cookie_string
        
        if not cookie_str:
            cookie_str = os.environ.get('LINKEDIN_COOKIES')
        
        if not cookie_str:
            print("❌ Error: No cookie provided. Pass cookie_string or set LINKEDIN_COOKIES env var.")
            return

        if not cookie_str:
            return

        # Simple parsing of cookie string "key=value; key2=value2"
        cookies = {}
        for item in cookie_str.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                cookies[k] = v.strip('"') # Strip quotes if present
        
        self.session.cookies.update(cookies)
        
        # Extract JSESSIONID for CSRF token
        self.csrf_token = cookies.get('JSESSIONID')
        if not self.csrf_token:
                print("⚠️  Warning: JSESSIONID not found in cookies. Requests might fail.")
        if self.csrf_token:
            # CSRF token loaded stealthily
            pass

    def log_error(self, error: str):
        """Log error messages to console (Vercel safe)."""
        print(f"[{datetime.now()}] ERROR {error}")
        # with open("logs/error.log", "a", encoding='utf-8') as f:
        #     f.write(f"{datetime.now()} ERROR {error}\n")
    
    def init_db(self):
        """Initialize connection to Supabase (handled by singleton)."""
        # No local DB initialization needed for Supabase
        pass

    def is_job_dismissed(self, job_id):
        """Check if job is already in the database."""
        return db.is_job_dismissed(job_id)

    def save_dismissed_job(self, job_id, title, company, location, reason, job_url, company_url, is_reposted=False, listed_at=None):
        """Save dismissed job to database."""
        db.save_dismissed_job(job_id, title, company, location, reason, None, company_url, is_reposted, listed_at, self.user_id)
            
    def delete_dismissed_job(self, job_id):
        """Remove a job from the dismissed jobs database."""
        return db.delete_dismissed_job(job_id)

    def dismiss_job(self, job_id, title, company, location, dismiss_urn=None, reason=None, job_url=None, company_url=None, is_reposted=False, listed_at=None):
        """Dismiss a job using Voyager API. Returns job data dict if successful, None otherwise."""
        print(f"🚫 Dismissing job: {title} at {company} (ID: {job_id})...")
        
        # Construct payload
        # Use provided URN or construct it
        urn = dismiss_urn if dismiss_urn else f"urn:li:fsd_jobPostingRelevanceFeedback:urn:li:fsd_jobPosting:{job_id}"
        
        payload = {
            "jobPostingRelevanceFeedbackUrn": urn,
            "channel": "JOB_SEARCH"
        }
        
        try:
            response = self.session.post(
                DISMISS_URL,
                json=payload,
                impersonate="chrome136",
                timeout=30
            )
            
            if response.status_code in [200, 201, 204]:
                print(f"   ✅ Successfully dismissed on LinkedIn")
                # Return job data for batch save later
                return {
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "dismiss_reason": reason,
                    "company_linkedin": company_url,
                    "is_reposted": is_reposted,
                    "listed_at": listed_at,
                    "dismissed_at": datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat(),
                    "user_id": self.user_id
                }
            else:
                print(f"   ❌ Failed to dismiss on LinkedIn: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error dismissing job: {e}")
            return None
            
    def undo_dismiss(self, job_id):
        """Undo dismissal of a job using Voyager API and remove from DB."""
        print(f"🔄 Undoing dismissal for Job ID: {job_id}...")
        
        # Construct payload
        # Reconstruct URN from ID
        # urn:li:fsd_jobPostingRelevanceFeedback:urn:li:fsd_jobPosting:<id>
        urn = f"urn:li:fsd_jobPostingRelevanceFeedback:urn:li:fsd_jobPosting:{job_id}"
        
        payload = {
            "jobPostingRelevanceFeedbackUrn": urn,
            "channel": "JOB_SEARCH"
        }
        
        try:
            response = self.session.post(
                UNDO_DISMISS_URL,
                json=payload,
                impersonate="chrome136",
                timeout=30
            )
            
            if response.status_code in [200, 201, 204]:
                print(f"   ✅ Successfully restored job on LinkedIn")
                self.delete_dismissed_job(job_id)
                return True
            else:
                print(f"   ❌ Failed to restore on LinkedIn: {response.status_code}")
                # print(f"   {response.text[:200]}") # Less verbose
                return False
                
        except Exception as e:
            print(f"   ❌ Error restoring job: {e}")
            return False

    def fetch_job_description(self, job_id):
        """Fetch job description using GraphQL."""
        # Query ID from user's CURL
        query_id = 'voyagerJobsDashJobPostingDetailSections.5b0469809f45002e8d68c712fd6e6285'
        url = 'https://www.linkedin.com/voyager/api/graphql'
        
        # Variables: (cardSectionTypes:List(JOB_DESCRIPTION_CARD),jobPostingUrn:urn:li:fsd_jobPosting:<id>,includeSecondaryActionsV2:true)
        # Note: The URN value must be URL encoded
        urn = f"urn:li:fsd_jobPosting:{job_id}"
        encoded_urn = urllib.parse.quote(urn)
        variables_str = f"(cardSectionTypes:List(JOB_DESCRIPTION_CARD),jobPostingUrn:{encoded_urn},includeSecondaryActionsV2:true)"
        
        full_url = f"{url}?variables={variables_str}&queryId={query_id}"
        
        print(f"   📄 Fetching description for Job {job_id}...")
        
        try:
            response = self.session.get(
                full_url,
                impersonate="chrome136",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse: Look in 'included' for urn:li:fsd_jobDescription:<job_id>
                try:
                    included = data.get('included', [])
                    target_urn = f"urn:li:fsd_jobDescription:{job_id}"
                    
                    for item in included:
                        if item.get('entityUrn') == target_urn:
                            desc_text = item.get('descriptionText', {}).get('text')
                            if desc_text:
                                return desc_text
                                
                    print(f"   ⚠️ Description URN {target_urn} not found in response.")
                except Exception as e:
                    print(f"   ⚠️ Error parsing description: {e}")
            else:
                print(f"   ⚠️ Failed to fetch description: {response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Error requesting description: {e}")
            
        return None

    def get_earliest_duplicate_job_id(self, title, company):
        """Find the earliest dismissed job with same title and company."""
        return db.get_earliest_duplicate(title, company)

    def log_info(self, info: str):
        """Log info messages to console (Vercel safe)."""
        print(f"[{datetime.now()}] INFO {info}")
        # with open("logs/info.log", "a", encoding='utf-8') as f:
        #     f.write(f"{datetime.now()} INFO {info}\n")
            
    def get_filter_clusters(self, geo_id):
        """Fetch secondary filter clusters (populatedPlace) for a given Master GeoID."""
        url = "https://www.linkedin.com/voyager/api/voyagerJobsDashSearchFilterClustersResource"
        decoration_id = "com.linkedin.voyager.dash.deco.search.SearchFilterCluster-44"
        
        # query=(origin:JOB_SEARCH_PAGE_JOB_FILTER,locationUnion:(geoId:{geo_id}),selectedFilters:(sortBy:List(R)),spellCorrectionEnabled:true)
        query_parts = [
            "origin:JOB_SEARCH_PAGE_JOB_FILTER",
            f"locationUnion:(geoId:{geo_id})",
            "selectedFilters:(sortBy:List(R))",
            "spellCorrectionEnabled:true"
        ]
        query_string = f"({','.join(query_parts)})"
        full_url = f"{url}?decorationId={decoration_id}&q=filters&query={query_string}"
        
        try:
            response = self.session.get(full_url, impersonate="chrome136", timeout=30)
            if response.status_code == 200:
                data = response.json()
                # Normalized API wraps elements in another 'data' key
                elements = data.get('data', {}).get('elements', [])
                candidates = []
                
                for el in elements:
                    groups = el.get('secondaryFilterGroups', [])
                    for group in groups:
                        filters = group.get('filters', [])
                        for f in filters:
                            if f.get('parameterName') == 'populatedPlace':
                                values = f.get('secondaryFilterValues', [])
                                for val in values:
                                    display_name = val.get('displayName', '')
                                    candidates.append({
                                        'id': val.get('value'),
                                        'name': display_name,
                                        'corrected_name': val.get('accessibilityText') or display_name
                                    })
                                    
                if candidates:
                    # Save candidates to DB
                    db.save_geo_candidates(geo_id, candidates)

                return candidates
            else:
                print(f"   ⚠️ Error fetching clusters: Status {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ Exception fetching clusters: {e}")
        return []

    def refine_location(self, location_name, master_geo_id):
        """Step 2: Refine Master GeoID to specific Populated Place ID."""
        print(f"   🔍 Refine: Fetching populated places for GeoID {master_geo_id}...")
        
        # Check geo_candidates cache first
        candidates = db.get_geo_candidates(master_geo_id)
        if candidates:
             print(f"   📍 Geo Candidates cache hit for {master_geo_id}")
        else:
             candidates = self.get_filter_clusters(master_geo_id) # Fallback to API call

        if not candidates:
            print("   ⚠️ No populated places found. Using Master GeoID.")
            return master_geo_id, None
            
        # Match Logic
        # User input: "Toronto, Ontario, Canada"
        # Candidates: ["Toronto, ON", "North York, ON", ...]
        # Simple heuristic: Split input by comma, take first part (City), check if candidate starts with it.
        
        city_key = location_name.split(',')[0].strip().lower()
        
        best_match = None
        
        for cand in candidates:
            c_name = cand['name'].lower()
            # 1. Exact Match (unlikely with state abbr differences)
            if c_name == location_name.lower():
                best_match = cand
                break
                
            # 2. Candidate starts with City Key (e.g. "toronto, on" starts with "toronto")
            if c_name.startswith(city_key):
                # Ensure boundary (check if next char is punctuation or end)
                # e.g. "Toronto" matches "Toronto, ON" but not "TorontoXYZ"
                remaining = c_name[len(city_key):]
                if not remaining or remaining[0] in [',', ' ', '-']:
                    best_match = cand
                    break # Take the first valid city match (usually sorted by relevance)
        
        if best_match:
            print(f"   ✅ Refined to: {best_match['name']} ({best_match['id']})")
            query = location_name.strip().title() # Use title for consistency
            try:
                db.update_geo_cache_override(location_name.strip().title(), best_match['id'])
            except Exception as e:
                print(f"   ⚠️ Cache update error during refinement: {e}")
            return best_match['id'], True
            
        print(f"   ⚠️ No match for '{location_name}' in candidates. Using Master GeoID.")
        return master_geo_id, False

    def resolve_geo_id(self, location_name):
        """Get LinkedIn GeoID for a location name, with local SQLite caching."""
        if not location_name or location_name.lower() == 'worldwide':
            return None, False
            
        query = location_name.strip().title() # Use title for consistency
        
        # Check cache
        row = db.get_geo_cache(query)
        if row:
            master_id = row.get('master_geo_id')
            pp_id = row.get('populated_place_id')
            final_id = pp_id if pp_id else master_id
            is_refined = pp_id is not None
            print(f"   📍 Cache hit: {location_name} (ID: {final_id}) {'[REFINED]' if is_refined else ''}")
            return final_id, is_refined

        print(f"📍 Resolving location: {location_name}...")
        
        # 1. Step 0: Check for direct candidate match (Optimized)
        match = db.get_candidate_by_corrected_name(query)
        if match:
            pp_id = match['pp_id']
            master_id = match['master_geo_id']
            print(f"   ✅ Direct candidate match found: {pp_id} (Master: {master_id})")
            # Save to cache automatically to avoid future candidate hits for this exact query
            try:
                db.save_geo_cache(query, master_id, pp_id)
            except Exception as e:
                print(f"   ⚠️ Scraper Warning (Save Geo Cache): {e}")
                pass
            return pp_id, True

        # 2. Step 1: Resolve Master GeoID
        url = 'https://www.linkedin.com/voyager/api/graphql'
        query_id = 'voyagerSearchDashReusableTypeahead.4c7caa85341b17b470153ad3d1a29caf'
        
        encoded_location = urllib.parse.quote(location_name)
        geo_types = "List(POSTCODE_1,POSTCODE_2,POPULATED_PLACE,ADMIN_DIVISION_1,ADMIN_DIVISION_2,COUNTRY_REGION,MARKET_AREA,COUNTRY_CLUSTER)"
        variables_str = f"(keywords:{encoded_location},query:(typeaheadFilterQuery:(geoSearchTypes:{geo_types}),typeaheadUseCase:JOBS),type:GEO)"
        full_url = f"{url}?includeWebMetadata=true&variables={variables_str}&queryId={query_id}"
        
        master_geo_id = None
        
        try:
            response = self.session.get(full_url, impersonate="chrome136", timeout=30)
            if response.status_code == 200:
                data = response.json()
                elements = data.get('data', {}).get('data', {}).get('searchDashReusableTypeaheadByType', {}).get('elements', [])
                
                for item in elements:
                    target = item.get('target', {})
                    if '*geo' in target:
                        geo_urn = target.get('*geo')
                        master_geo_id = geo_urn.split(':')[-1]
                        print(f"   ✅ Master GeoID: {target.get('*geo')} ({master_geo_id})")
                        break # Take first result
        except Exception as e:
            print(f"   ⚠️ Error resolving Master GeoID: {e}")
            
        if not master_geo_id:
            print("   ⚠️ Could not resolve Master GeoID.")
            return None, False
            
        # 3. Step 2: Refine to Populated Place
        pp_id, is_refined = self.refine_location(location_name, master_geo_id)
        
        final_id = pp_id if is_refined else master_geo_id
        
        # 4. Save to Cache
        try:
            # Only cache pp_id if it was actually refined from the master id
            cache_pp_id = pp_id if is_refined else None
            db.save_geo_cache(location_name.strip().title(), master_geo_id, cache_pp_id)
        except Exception as e:
            print(f"   ⚠️ Cache write error: {e}")
            
        return final_id, is_refined

        return final_id, is_refined

    def fetch_page(self, start, count=25, geo_id=None, is_refined=False, sort_by="DD", time_range=None):
        """Fetch a single page of jobs at a specific offset."""
        print(f"🌐 Fetching jobs starting at {start}...")
        
        # Construct Query parts
        filter_list = [f"sortBy:List({sort_by})"]
        
        if time_range:
            filter_list.append(f"timePostedRange:List({time_range})")
        
        if self.workplace_type:
            # 1=On-site, 2=Remote, 3=Hybrid
            wt_str = ",".join(map(str, self.workplace_type))
            filter_list.append(f"workplaceType:List({wt_str})")

        if self.easy_apply:
            filter_list.append("applyWithLinkedin:List(true)")
        
        # Location Filter (populatedPlace vs locationUnion)
        # If refined, use populatedPlace in selectedFilters
        # If not refined, use locationUnion in primary query
        
        geo_query_part = None
        if geo_id:
            if is_refined:
                filter_list.append(f"populatedPlace:List({geo_id})")
            else:
                geo_query_part = f"locationUnion:(geoId:{geo_id})"

        filters_str = ",".join(filter_list)
        
        query_parts = [
            "origin:JOB_SEARCH_PAGE_JOB_FILTER",
            "spellCorrectionEnabled:true"
        ]
        
        if geo_query_part:
            query_parts.append(geo_query_part)
            
        query_parts.append(f"selectedFilters:({filters_str})")
        
        if self.keywords:
            encoded_kw = urllib.parse.quote(self.keywords)
            query_parts.append(f"keywords:{encoded_kw}")
        
        # Remove locationUnion logic, fallback to keyword location if no geo_id
        if not geo_id and self.location:
             encoded_loc = urllib.parse.quote(self.location)
             query_parts.append(f"keywords:{encoded_loc}") 

        query_string = f"({','.join(query_parts)})"
        
        # Updated decorationId to be more comprehensive (non-lite) to get footerItems and listed_at
        decoration_id = "com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-76"
        q_param = "jobSearch"
        
        full_url = f"{VOYAGER_API_URL}?decorationId={decoration_id}&count={count}&q={q_param}&query={query_string}&servedEventEnabled=false&start={start}"
        # print(f"🔗 Request URL: {full_url}")

        try:
            # RETRY LOGIC: Simple retry for 500/timeout errors
            retries = 3
            for attempt in range(retries):
                try:
                    response = self.session.get(
                        full_url,
                        impersonate="chrome136",
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        break
                    elif response.status_code in [429, 500, 502, 503, 504]:
                         print(f"⚠️  API Error {response.status_code}. Retrying ({attempt+1}/{retries})...")
                         sleep(2 * (attempt + 1))
                    else:
                        print(f"❌ API Error: {response.status_code}")
                        return [], 0
                except Exception as req_err:
                     print(f"⚠️  Request Error: {req_err}. Retrying ({attempt+1}/{retries})...")
                     sleep(2 * (attempt + 1))
            else:
                # Loop exhausted
                print(f"❌ Failed to fetch page at {start} after {retries} retries.")
                return [], 0

            data = response.json()
            
            # Get Total Jobs (useful on first page)
            total_jobs = data.get('data', {}).get('paging', {}).get('total')
            
            # --- Parsing Logic Refactored ---
            # 1. Build Lookup Map from 'included'
            included = data.get('included', [])
            urn_map = {item.get('entityUrn'): item for item in included if 'entityUrn' in item}
            
            # 2. Iterate 'elements' (Ordered list of hits)
            elements = data.get('data', {}).get('elements', [])
            page_jobs = []
            
            for element in elements:
                # element has 'jobCardUnion': { '*jobPostingCard': 'urn:...' }
                card_urn = element.get('jobCardUnion', {}).get('*jobPostingCard')
                if not card_urn:
                    continue
                    
                card = urn_map.get(card_urn)
                if not card:
                    continue
                    
                # Extract Details from JobPostingCard
                # Title
                title = card.get('title', {}).get('text', None)
                
                # Company (Primary Description)
                company = card.get('primaryDescription', {}).get('text', None)
                
                # Location (Secondary Description)
                location = card.get('secondaryDescription', {}).get('text', None)
                
                # Job ID
                # jobPostingUrn: "urn:li:fsd_jobPosting:4346967414"
                job_posting_urn = card.get('jobPostingUrn', '')
                if not job_posting_urn:
                    job_posting_urn = card.get('*jobPosting', '')

                job_id = job_posting_urn.split(':')[-1]
                
                # Check Reposted Status
                is_reposted = False
                posting_urn = card.get('*jobPosting')
                posting_data = None
                if posting_urn:
                    posting_data = urn_map.get(posting_urn)
                    if posting_data:
                        is_reposted = posting_data.get('repostedJob', False)

                # Check Easy Apply Status & Listed Date
                is_easy_apply = False
                is_early_applicant = False
                listed_at = None
                
                # Fallback 1: Check direct posting data (often contains accurate timestamps)
                if posting_data:
                    # Common fields in JobPosting object
                    ts_ms = (posting_data.get('listedAt') or 
                             posting_data.get('createdAt') or 
                             posting_data.get('firstListedAt') or
                             posting_data.get('listedAtTimestamp'))
                    if ts_ms:
                        try:
                            dt = datetime.fromtimestamp(ts_ms / 1000, timezone(timedelta(hours=-5)))
                            listed_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception: pass

                # Fallback 2: Robust Footer Check
                footer_items = card.get('footerItems', [])
                for item in footer_items:
                    item_type = str(item.get('type', ''))
                    if item_type == 'EASY_APPLY_TEXT':
                        is_easy_apply = True
                    elif item_type == 'APPLICANT_COUNT_TEXT':
                        text = item.get('text', {}).get('text', '').lower()
                        if 'early applicant' in text:
                            is_early_applicant = True
                    elif 'DATE' in item_type or 'TIME' in item_type:
                        ts_ms = item.get('timeAt') or item.get('listedAt')
                        if ts_ms and not listed_at:
                            try:
                                dt = datetime.fromtimestamp(ts_ms / 1000, timezone(timedelta(hours=-5)))
                                listed_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except Exception: pass
                
                # Fallback 3: Aggressive deep search for 13-digit timestamps in the card
                if not listed_at:
                    def find_ts(obj):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if isinstance(v, (int, float)) and 10**12 < v < 2*10**12: # 13-digit ms TS
                                    return v
                                res = find_ts(v)
                                if res: return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_ts(item)
                                if res: return res
                        return None
                    
                    deep_ts = find_ts(card)
                    if deep_ts:
                        try:
                            dt = datetime.fromtimestamp(deep_ts / 1000, timezone(timedelta(hours=-5)))
                            listed_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception: pass
                
                if not listed_at:
                     # Final attempt: Look into Relevance Insight
                     ts_ms = card.get('relevanceInsight', {}).get('timeAt')
                     if ts_ms:
                         try:
                             dt = datetime.fromtimestamp(ts_ms / 1000, timezone(timedelta(hours=-5)))
                             listed_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                         except Exception: pass

                # Debug log (only if NULL to avoid spam)
                if not listed_at:
                    print(f"   ⚠️  Could not find listing date for '{title}'. (Posting keys: {list(posting_data.keys()) if posting_data else 'N/A'}, Card keys: {list(card.keys())})")
                
                # Check Actively Reviewing Status
                is_actively_reviewing = False
                relevance_insight = card.get('relevanceInsight') or {}
                insight_text = relevance_insight.get('text', {}).get('text', '').lower()
                if 'actively reviewing' in insight_text:
                    is_actively_reviewing = True

                # Check for Applied / Viewed Status
                # Entity Urn: urn:li:fsd_jobSeekerJobState:<job_id>
                is_applied = False
                is_viewed = False
                seeker_state_urn = f"urn:li:fsd_jobSeekerJobState:{job_id}"
                seeker_state = urn_map.get(seeker_state_urn)
                
                if seeker_state:
                    actions = seeker_state.get('jobSeekerJobStateActions', [])
                    for action in actions:
                        state_enum = action.get('jobSeekerJobStateEnums')
                        if state_enum == 'APPLIED':
                            is_applied = True
                        elif state_enum == 'VIEWED':
                            is_viewed = True
                
                # Company LinkedIn URL (logo -> actionTarget)
                # "actionTarget": "https://www.linkedin.com/company/cleese-catering2023/life"
                company_url = card.get('logo', {}).get('actionTarget', '').replace('/life', '')
                
                # Job URL
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
                
                # Dismissal URN (Optional but good to have if present)
                # It's usually in primaryActionsUnions -> dismissJobAction -> jobPostingRelevanceFeedbackUrn
                dismiss_urn = None
                is_already_dismissed = False
                primary_actions = card.get('primaryActionsUnions', [])
                for action in primary_actions:
                    dismiss_action = action.get('dismissJobAction')
                    if dismiss_action:
                        dismiss_urn = dismiss_action.get('jobPostingRelevanceFeedbackUrn')
                        # Check LinkedIn-native dismissal status
                        feedback_obj = urn_map.get(dismiss_urn)
                        if feedback_obj and feedback_obj.get('dismissed') is True:
                            is_already_dismissed = True
                        break
                        
                job_data = {
                    'job_id': job_id,
                    'title': title,
                    'company': company,
                    'location': location,
                    'dismiss_urn': dismiss_urn,
                    'job_url': job_url,
                    'company_linkedin': company_url,
                    'is_reposted': is_reposted,
                    'listed_at': listed_at,
                    'is_easy_apply': is_easy_apply,
                    'is_early_applicant': is_early_applicant,
                    'is_actively_reviewing': is_actively_reviewing,
                    'is_applied': is_applied,
                    'is_viewed': is_viewed,
                    'is_already_dismissed': is_already_dismissed
                }
                page_jobs.append(job_data)

            if not page_jobs:
                print(f"⚠️  No more jobs found at offset {start}.")
                
            print(f"✅ Found {len(page_jobs)} jobs on page starting at {start}.")
            return page_jobs, total_jobs
            
        except Exception as e:
            print(f"❌ Error fetching page: {e}")
            self.log_error(f"Error fetching page {start}: {e}")
            return [], 0

    def process_page_result(self, page_jobs):
        """Process a single page of results. Returns (stats_tuple, list_of_dismissed_job_dicts)."""
        if not page_jobs: return (0, 0, 0, 0, 0, 0, 0, 0, 0), []

        processed = dismissed = skipped = reposted = easy = early = reviewing = applied = viewed = 0
        dismissed_jobs_data = []  # Collect for batch save
        
        # Batch check dismissal
        job_ids = [j.get('job_id') for j in page_jobs if j.get('job_id')]
        dismissed_ids = db.get_dismissed_job_ids(job_ids, self.user_id) if job_ids else set()

        # Stats for this page
        reposted = sum(1 for j in page_jobs if j.get('is_reposted'))
        easy = sum(1 for j in page_jobs if j.get('is_easy_apply'))
        early = sum(1 for j in page_jobs if j.get('is_early_applicant'))
        reviewing = sum(1 for j in page_jobs if j.get('is_actively_reviewing'))
        applied = sum(1 for j in page_jobs if j.get('is_applied'))
        viewed = sum(1 for j in page_jobs if j.get('is_viewed') and not j.get('is_applied'))
        
        print(f"📝 Processing batch with {len(page_jobs)} jobs ({reposted} reposted, {easy} easy apply, {early} early)...")

        for job in tqdm(page_jobs, desc="Filtering Jobs", leave=False):
            title = job.get('title', None)
            job_id = job.get('job_id')
            company = job.get('company', None)
            location = job.get('location', None)
            dismiss_urn = job.get('dismiss_urn')
            job_url = job.get('job_url')
            company_url = job.get('company_linkedin')
            is_reposted = job.get('is_reposted', False)
            listed_at = job.get('listed_at')
            
            processed += 1
            
            # 1. Check if already in OUR database (Skipped)
            if job_id in dismissed_ids:
                skipped += 1
                continue
            
            # 2. Check LinkedIn-native dismissal (Sync to DB if not present)
            if job.get('is_already_dismissed'):
                print(f"   📥 Syncing LinkedIn-native dismissal: '{title}'")
                sync_data = {
                    'job_id': job_id,
                    'title': title,
                    'company': company,
                    'location': location,
                    'dismiss_reason': "linkedin_native_dismissal",
                    'company_linkedin': company_url,
                    'is_reposted': is_reposted,
                    'listed_at': listed_at,
                    'user_id': self.user_id,
                    'dismissed_at': datetime.now(timezone(timedelta(hours=-5))).replace(microsecond=0).isoformat()
                }
                dismissed_jobs_data.append(sync_data)
                dismissed += 1
                continue
                
            # 3. Regular Filtering logic...
            should_dismiss = False
            dismiss_reason = None
            
            # Check Title Blocklist
            for keyword in self.dismiss_titles:
                if keyword.lower() in title.lower():
                    should_dismiss = True
                    dismiss_reason = "job_title" 
                    print(f"   🔍 Match found: '{keyword}' in Title: '{title}'")
                    break
            
            # Check Company Blocklist
            if not should_dismiss:
                for keyword in self.dismiss_companies:
                    if company_url and keyword.lower() in company_url.lower():
                        should_dismiss = True
                        dismiss_reason = "company"
                        print(f"   🔍 Match found: '{keyword}' in Company URL: '{company_url}'")
                        break
            
            # Check Auto-Dismiss for Applied Jobs
            if not should_dismiss and job.get('is_applied'):
                should_dismiss = True
                dismiss_reason = "applied"
                print(f"   🚫 Auto-dismissing already applied job: '{title}'")
                
            # Description-Based Deduplication
            if not should_dismiss:
                dup_id = self.get_earliest_duplicate_job_id(title, company)
                if dup_id and dup_id != job_id:
                    print(f"   🤔 Found potential duplicate in DB (ID: {dup_id}). Comparing descriptions...")
                    if self.job_delay > 0: sleep(self.job_delay)
                    desc_new = self.fetch_job_description(job_id)
                    desc_old = self.fetch_job_description(dup_id)
                    
                    if desc_new and desc_old:
                        desc_new_clean = desc_new.strip()
                        desc_old_clean = desc_old.strip()
                        
                        # Use SequenceMatcher for fuzzy comparison
                        similarity = difflib.SequenceMatcher(None, desc_new_clean, desc_old_clean).ratio()
                        
                        if similarity >= 0.95: # 95% similarity threshold
                            should_dismiss = True
                            dismiss_reason = f"duplicate_description:matched_{dup_id}_sim_{similarity:.3f}"
                            print(f"   🚫 Text descriptions are {similarity*100:.1f}% similar! Deduplicating...")
                        else:
                            print(f"   ✅ Descriptions differ (similarity: {similarity*100:.1f}%). Not a duplicate.")
                    else:
                        print(f"   ⚠️ Could not fetch one or both descriptions for comparison.")
            
            # 4. Perform Dismissal on LinkedIn
            if should_dismiss:
                if self.job_delay > 0: sleep(self.job_delay)
                job_data = self.dismiss_job(job_id, title, company, location, dismiss_urn, reason=dismiss_reason, job_url=job_url, company_url=company_url, is_reposted=is_reposted, listed_at=listed_at)
                if job_data:
                    dismissed += 1
                    dismissed_jobs_data.append(job_data)
        
        return (processed, dismissed, skipped, reposted, easy, early, reviewing, applied, viewed), dismissed_jobs_data

    def process_jobs(self):
        """Main processing loop: Fetch (Concurrent) -> Filter -> Dismiss -> Batch Save."""
        if not self.dismiss_titles and not self.dismiss_companies:
            print("ℹ️ No blocklists provided. Scraping only...")
        
        # Init counters
        total_processed = 0
        total_dismissed = 0
        total_skipped = 0
        total_reposted = 0
        total_easy = 0
        total_early = 0
        total_reviewing = 0
        total_applied = 0
        total_viewed = 0
        all_dismissed_jobs = []  # Collect for batch save
        
        # Resolve Location first
        geo_id = None
        is_refined = False
        if self.location:
             geo_id, is_refined = self.resolve_geo_id(self.location)

        # Sort Logic
        sort_by = "R" if self.relevant else "DD"
        time_range = None
        if self.time_filter == '30m': time_range = "r1800"
        elif self.time_filter == '1h': time_range = "r3600"
        elif self.time_filter == '8h': time_range = "r28800"
        elif self.time_filter == '24h': time_range = "r86400"
        elif self.time_filter == '2d': time_range = "r172800"
        elif self.time_filter == '3d': time_range = "r259200"
        elif self.time_filter == 'week': time_range = "r604800"
        elif self.time_filter == 'month': time_range = "r2592000"

        # 1. Fetch First Page (Synchronous) to get Total Count
        print("🚀 Fetching Page 0 to determine scope...")
        page0_jobs, total_jobs = self.fetch_page(0, count=25, geo_id=geo_id, is_refined=is_refined, sort_by=sort_by, time_range=time_range)
        
        if not page0_jobs:
            print("❌ No jobs found or API error on first page.")
            return

        if total_jobs:
            print(f"📊 Total jobs available: {total_jobs}")
        
        # Process Page 0
        (p, d, s, rep, easy, early, rev, app, view), dismissed_data = self.process_page_result(page0_jobs)
        total_processed += p
        total_dismissed += d
        total_skipped += s
        total_reposted += rep
        total_easy += easy
        total_early += early
        total_reviewing += rev
        total_applied += app
        total_viewed += view
        all_dismissed_jobs.extend(dismissed_data)

        # 2. Concurrent Fetch for remaining pages
        max_workers = 3
        
        # Use total_jobs as the hard limit (API already told us how many exist)
        # Also respect user's limit_jobs if set
        if total_jobs:
            max_offset = min(total_jobs, self.limit_jobs) if self.limit_jobs > 0 else total_jobs
        else:
            max_offset = self.limit_jobs if self.limit_jobs > 0 else 1000
        
        # Determine pages needed - only request offsets that could have jobs
        # We already did start=0. Next is 25, 50, ... up to max_offset
        offsets = list(range(25, max_offset, 25))
        
        if offsets:
            print(f"🚀 Starting concurrent fetch for {len(offsets)} pages with {max_workers} workers...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_offset = {
                    executor.submit(self.fetch_page, start, 25, geo_id, is_refined, sort_by, time_range): start 
                    for start in offsets
                }
                
                # Process as they complete
                for future in concurrent.futures.as_completed(future_to_offset):
                    start = future_to_offset[future]
                    try:
                        page_jobs, _ = future.result()
                        if page_jobs:
                            (p, d, s, rep, easy, early, rev, app, view), dismissed_data = self.process_page_result(page_jobs)
                            total_processed += p
                            total_dismissed += d
                            total_skipped += s
                            total_reposted += rep
                            total_easy += easy
                            total_early += early
                            total_reviewing += rev
                            total_applied += app
                            total_viewed += view
                            all_dismissed_jobs.extend(dismissed_data)
                        else:
                            print(f"⚠️ Empty result for offset {start}")
                    except Exception as exc:
                        print(f"❌ Exception fetching offset {start}: {exc}")
        
        # 3. Batch Save all dismissed jobs to Supabase
        if all_dismissed_jobs:
            print(f"\n💾 Batch saving {len(all_dismissed_jobs)} dismissed jobs to Supabase...")
            db.batch_save_dismissed_jobs(all_dismissed_jobs)
        
        print(f"\n✨ Done! Processed {total_processed} jobs. Dismissed {total_dismissed} jobs. Skipped {total_skipped}.")
        print(f"📊 Stats: Reposted: {total_reposted}, Easy: {total_easy}, Early: {total_early}, Reviewing: {total_reviewing}, Applied: {total_applied}, Viewed: {total_viewed}")

    def close_session(self):
        if hasattr(self, 'session'):
            self.session.close()
        if hasattr(self, 'conn'):
            self.conn.close()

def main():
    parser = argparse.ArgumentParser(description='LinkedIn Job Cleaner - Dismiss Irrelevant Jobs')
    parser.add_argument('--keywords', '-k', type=str, default='', help='Job search keywords (e.g. "python developer")')
    parser.add_argument('--location', '-l', type=str, default='Canada', help='Job location')
    parser.add_argument('--limit', type=int, default=25, help='Max jobs to process (default: 25)')
    parser.add_argument('--dismiss', '-d', type=str, help='Comma-separated keywords to dismiss by Title')
    parser.add_argument('--block-company', '-bc', type=str, help='Comma-separated companies to block')
    parser.add_argument('--relevance', action='store_true', help='Sort by relevance (default: Most Recent)')
    parser.add_argument('--time', type=str, choices=['all', '24h', 'week', 'month'], default='all', help='Time posted filter')
    parser.add_argument('--easy-apply', action='store_true', help='Filter for Easy Apply jobs')
    
    # Undo Options
    parser.add_argument('--undo-id', type=str, help='Undo dismissal for a specific Job ID')
    parser.add_argument('--undo-title', type=str, help='Undo dismissal for all locally dismissed jobs matching title (substring)')
    
    args = parser.parse_args()
    
    dismiss_titles = []
    dismiss_companies = []
    
    # Read from Supabase blocklists
    try:
        dismiss_titles = db.get_blocklist("job_title")
        dismiss_companies = db.get_blocklist("company_linkedin")
        if dismiss_titles:
            print(f"🚫 Loaded {len(dismiss_titles)} title keywords from Supabase")
        if dismiss_companies:
            print(f"🚫 Loaded {len(dismiss_companies)} company keywords from Supabase")
    except Exception as e:
        print(f"⚠️  Error reading blocklists from Supabase: {e}")

    # Add CLI args
    if args.dismiss:
        dismiss_titles.extend(args.dismiss.split(','))
    
    if args.block_company:
        dismiss_companies.extend(args.block_company.split(','))
    
    # Remove duplicates
    dismiss_titles = list(set(dismiss_titles))
    dismiss_companies = list(set(dismiss_companies))
    
    scraper = LinkedInScraper(
        keywords=args.keywords,
        location=args.location,
        limit_jobs=args.limit,
        dismiss_keywords=dismiss_titles if not args.keywords and not args.undo_id and not args.undo_title else dismiss_titles, # Only use global blocklist if regular run
        dismiss_companies=args.block_company.split(',') if args.block_company else dismiss_companies,
        recent=not args.relevance,
        time_filter=args.time,
        easy_apply=args.easy_apply
    )
    
    try:
        # Handle Undo Modes
        if args.undo_id:
            scraper.undo_dismiss(args.undo_id)
        elif args.undo_title:
            # Search local DB for matches
            print(f"🔍 Searching local DB for dismissed jobs matching title: '{args.undo_title}'...")
            scraper.cursor.execute("SELECT job_id, title FROM dismissed_jobs WHERE title LIKE ?", (f"%{args.undo_title}%",))
            matches = scraper.cursor.fetchall()
            
            if not matches:
                print("   No matching jobs found in local database.")
            else:
                print(f"   Found {len(matches)} matching jobs. Attempting to restore...")
                for job_id, title in matches:
                    print(f"   Target: {title} ({job_id})")
                    scraper.undo_dismiss(job_id)
                    sleep(1) # Be nice
                    
        # Regular Scraping Mode
        elif args.keywords or args.location:
             scraper.process_jobs()
        else:
             scraper.process_jobs()
             
    except KeyboardInterrupt:
        print("\n� Stopping...")
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
    finally:
        scraper.close_session()

if __name__ == "__main__":
    main()
