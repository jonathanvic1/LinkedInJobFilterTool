# LinkedIn Job Scraper Configuration
# Copy this file to config.py and modify the values as needed

# Search Parameters
KEYWORDS = "python developer"  # Job search keywords
LOCATION = "Canada"     # Job location
TIME_RANGE = "r86400"         # r86400 (24h), r604800 (1w), r2592000 (1m)
DISTANCE = ""                 # Distance in miles: 10, 25, 50, 75, 100

# Job Types (can be multiple)
# F: Full-time, CP: Part-time, CC: Contract, T: Temporary, CV: Volunteer
JOB_TYPES = ["F"]

# Work Location (can be multiple)
# 1: On-site, 2: Remote, 3: Hybrid
WORK_LOCATIONS = ["2", "3"]  # Remote and Hybrid

# Scraping Settings
LIMIT_JOBS = 100             # Maximum jobs to scrape (0 = no limit)
OUTPUT_FILE = "jobs.csv"     # Output filename

# Rate Limiting (seconds)
PAGE_DELAY = 0.5            # Delay between page requests
JOB_DELAY = 0.3             # Delay between job detail requests
