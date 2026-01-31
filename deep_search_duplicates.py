from database import db

# Search for 20 recently dismissed duplicates
res = db.client.table('dismissed_jobs').select('job_id, title, company, dismiss_reason')\
    .eq('dismiss_reason', 'duplicate_description')\
    .limit(20)\
    .execute()

for r in res.data:
    print(f"\n--- Checking Duplicate Job ID: {r['job_id']} ---")
    print(f"Title   : {repr(r['title'])}")
    print(f"Company : {repr(r['company'])}")
    
    # Try EXACT match first
    res_exact = db.client.table('dismissed_jobs').select('job_id, title, company, dismiss_reason, listed_at')\
        .eq('title', r['title'])\
        .eq('company', r['company'])\
        .order('listed_at', desc=False)\
        .execute()
    
    # If no other match, try trim match (Supabase might be ignoring trailing spaces in some contexts?)
    res_trim = db.client.table('dismissed_jobs').select('job_id, title, company, dismiss_reason, listed_at')\
        .ilike('title', f"%{r['title'].strip()}%")\
        .ilike('company', f"%{r['company'].strip()}%")\
        .order('listed_at', desc=False)\
        .execute()
        
    print(f"Exact Matches Found: {len(res_exact.data)}")
    for m in res_exact.data:
         print(f"  ID: {m['job_id']} | Reason: {m['dismiss_reason']} | Listed: {m['listed_at']}")
         
    if len(res_exact.data) == 1:
        print(f"Trim Matches Found: {len(res_trim.data)}")
        for m in res_trim.data:
             if m['job_id'] != r['job_id']:
                 print(f"  ID: {m['job_id']} | Title: {repr(m['title'])} | Company: {repr(m['company'])} | Reason: {m['dismiss_reason']}")
