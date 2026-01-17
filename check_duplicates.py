from linkedin_scraper import LinkedInScraper
import time
import argparse
import sys

def check_duplicates(target_title, target_company):
    scraper = LinkedInScraper()
    scraper.load_cookies()
    
    print(f"🔍 Querying DB for '{target_title}' at '{target_company}'...")
    
    # Use LIKE to handle trailing spaces or non-breaking spaces seen in DB output
    # Adding % wildcard to end of terms
    company_term = target_company.strip() + '%'
    title_term = target_title.strip() + '%'
    
    scraper.cursor.execute(
        "SELECT job_id, title, company FROM dismissed_jobs WHERE company LIKE ? AND title LIKE ?", 
        (company_term, title_term)
    )
    jobs = scraper.cursor.fetchall()
    
    if not jobs:
        print(f"❌ No jobs found in DB matching Title='{target_title}' and Company='{target_company}'.")
        return

    print(f"✅ Found {len(jobs)} jobs in DB.")
    
    descriptions = {}
    
    for job_id, title, company in jobs:
        print(f"   📄 Fetching description for {job_id} ({title} @ {company})...")
        desc = scraper.fetch_job_description(job_id)
        if desc:
            descriptions[job_id] = desc
        else:
            print(f"   ⚠️ Could not fetch description for {job_id}")
        time.sleep(1) # Be nice to API
        
    # Compare
    if not descriptions:
        print("❌ No descriptions fetched.")
        return
        
    base_id = list(descriptions.keys())[0]
    base_desc = descriptions[base_id]
    
    print(f"\n📊 Comparing against base job {base_id} (Length: {len(base_desc)}):")
    
    for job_id, desc in descriptions.items():
        if job_id == base_id: continue
        
        match = (desc.strip() == base_desc.strip())
        print(f"   👉 {job_id}: {'MATCH ✅' if match else 'NO MATCH ❌'} (Length: {len(desc)})")
        if not match:
            # Print diff snippet
            # Show first 100 chars of diff or something useful?
            # Keeping it simple as before
            print(f"      Diff starts: {desc[:50]}... vs ...{base_desc[:50]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check for duplicate job descriptions in the database.")
    parser.add_argument("--title", type=str, required=True, help="Job title to search for (supports partial match)")
    parser.add_argument("--company", type=str, required=True, help="Company name to search for (supports partial match)")
    
    args = parser.parse_args()
    
    check_duplicates(args.title, args.company)
