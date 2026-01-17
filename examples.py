#!/usr/bin/env python3
"""
Example usage of LinkedIn Job Scraper
"""

from linkedin_scraper import LinkedInScraper

def example_1_remote_python_jobs():
    """Example 1: Scrape remote Python developer jobs"""
    print("📝 Example 1: Remote Python Developer Jobs")
    
    scraper = LinkedInScraper(
        keywords="python developer",
        location="Canada",
        time_range="r86400",  # Last 24 hours
        job_type=["F"],       # Full-time only
        place=["2"],          # Remote only
        limit_jobs=25         # Limit to 25 jobs
    )
    
    try:
        jobs = scraper.scrape_jobs()
        if jobs:
            filename = scraper.save_to_csv(jobs, "remote_python_jobs.csv")
            print(f"✅ Saved {len(jobs)} jobs to {filename}")
        return jobs
    finally:
        scraper.close_session()

def example_2_data_science_jobs():
    """Example 2: Scrape data science jobs in major cities"""
    print("\n📝 Example 2: Data Science Jobs")
    
    scraper = LinkedInScraper(
        keywords="data scientist machine learning",
        location="San Francisco, CA",
        time_range="r604800",    # Last week
        job_type=["F", "CP"],    # Full-time and Part-time
        place=["2", "3"],        # Remote and Hybrid
        distance="50",           # Within 50 miles
        limit_jobs=30
    )
    
    try:
        jobs = scraper.scrape_jobs()
        if jobs:
            filename = scraper.save_to_csv(jobs, "data_science_jobs.csv")
            print(f"✅ Saved {len(jobs)} jobs to {filename}")
        return jobs
    finally:
        scraper.close_session()

def example_3_entry_level_jobs():
    """Example 3: Entry level software engineering jobs"""
    print("\n📝 Example 3: Entry Level Software Engineer Jobs")
    
    scraper = LinkedInScraper(
        keywords="software engineer entry level junior",
        location="Seattle, WA",
        time_range="r86400",     # Last 24 hours
        job_type=["F"],          # Full-time only
        place=["1", "2", "3"],   # All work locations
        limit_jobs=20
    )
    
    try:
        jobs = scraper.scrape_jobs()
        if jobs:
            filename = scraper.save_to_csv(jobs, "entry_level_jobs.csv")
            print(f"✅ Saved {len(jobs)} jobs to {filename}")
        return jobs
    finally:
        scraper.close_session()

def analyze_jobs(jobs, title="Job Analysis"):
    """Simple analysis of scraped jobs"""
    if not jobs:
        print(f"❌ No jobs to analyze for {title}")
        return
    
    print(f"\n📊 {title}")
    print(f"Total jobs: {len(jobs)}")
    
    # Analyze companies
    companies = [job.get('company') for job in jobs if job.get('company')]
    if companies:
        unique_companies = set(companies)
        print(f"Unique companies: {len(unique_companies)}")
        
        # Top companies
        from collections import Counter
        company_counts = Counter(companies)
        top_companies = company_counts.most_common(5)
        print("Top companies:")
        for company, count in top_companies:
            print(f"  • {company}: {count} jobs")
    
    # Analyze locations
    locations = [job.get('location') for job in jobs if job.get('location')]
    if locations:
        unique_locations = set(locations)
        print(f"Unique locations: {len(unique_locations)}")
    
    # Analyze employment types
    emp_types = [job.get('employment_type') for job in jobs if job.get('employment_type')]
    if emp_types:
        from collections import Counter
        type_counts = Counter(emp_types)
        print("Employment types:")
        for emp_type, count in type_counts.items():
            print(f"  • {emp_type}: {count} jobs")

def main():
    """Run all examples"""
    print("🚀 LinkedIn Job Scraper Examples")
    print("=" * 50)
    
    try:
        # Run examples
        python_jobs = example_1_remote_python_jobs()
        analyze_jobs(python_jobs, "Remote Python Jobs Analysis")
        
        ds_jobs = example_2_data_science_jobs()
        analyze_jobs(ds_jobs, "Data Science Jobs Analysis")
        
        entry_jobs = example_3_entry_level_jobs()
        analyze_jobs(entry_jobs, "Entry Level Jobs Analysis")
        
        print("\n🎉 All examples completed!")
        print("\nFiles created:")
        print("• remote_python_jobs.csv")
        print("• data_science_jobs.csv")
        print("• entry_level_jobs.csv")
        
    except KeyboardInterrupt:
        print("\n🛑 Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running examples: {str(e)}")

if __name__ == "__main__":
    main()
