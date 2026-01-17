#!/usr/bin/env python3
"""
Simple LinkedIn Job Scraper using configuration file
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from linkedin_scraper import LinkedInScraper

# Try to import configuration
try:
    from config import *
except ImportError:
    print("⚠️  Configuration file not found. Using default settings.")
    print("💡 Copy config_example.py to config.py and customize your settings.")
    
    # Default configuration
    KEYWORDS = "software engineer"
    LOCATION = "Canada"
    TIME_RANGE = "r86400"
    DISTANCE = ""
    JOB_TYPES = ["F"]
    WORK_LOCATIONS = ["2", "3"]
    LIMIT_JOBS = 50
    OUTPUT_FILE = "jobs.csv"

def main():
    print("🚀 Starting LinkedIn Job Scraper")
    print(f"🔍 Keywords: {KEYWORDS}")
    print(f"📍 Location: {LOCATION}")
    print(f"⏰ Time Range: {TIME_RANGE}")
    print(f"💼 Job Types: {JOB_TYPES}")
    print(f"🏠 Work Locations: {WORK_LOCATIONS}")
    print(f"📊 Limit: {LIMIT_JOBS if LIMIT_JOBS > 0 else 'No limit'}")
    print("-" * 50)
    
    # Create scraper
    scraper = LinkedInScraper(
        keywords=KEYWORDS,
        location=LOCATION,
        time_range=TIME_RANGE,
        distance=DISTANCE,
        job_type=JOB_TYPES,
        place=WORK_LOCATIONS,
        limit_jobs=LIMIT_JOBS,
        workplace_type=[] # Default to empty for CLI unless configured
    )
    
    try:
        # Scrape jobs
        jobs = scraper.scrape_jobs()
        
        if jobs:
            # Save results
            filename = scraper.save_to_csv(jobs, OUTPUT_FILE)
            
            if filename:
                print(f"\n🎉 Success! Scraped {len(jobs)} jobs")
                print(f"📁 Saved to: {filename}")
                
                # Print some statistics
                companies = [job.get('company') for job in jobs if job.get('company')]
                locations = [job.get('location') for job in jobs if job.get('location')]
                
                if companies:
                    unique_companies = len(set(companies))
                    print(f"🏢 Companies: {unique_companies} unique companies")
                
                if locations:
                    unique_locations = len(set(locations))
                    print(f"📍 Locations: {unique_locations} unique locations")
                    
            else:
                print("❌ Failed to save results")
        else:
            print("❌ No jobs found")
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
