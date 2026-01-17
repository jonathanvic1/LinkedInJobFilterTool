# LinkedIn Job Filter Tool

A robust Python-based tool designed to filter and manage job postings availability from LinkedIn. It provides a filtering mechanism to hide irrelevant jobs and focus on opportunities that match your specific criteria.

## Features

- 🔍 **Smart Filtering**: Dismiss irrelevant jobs and keep your feed clean
- 🚫 **Blocklists**: Automatically filter out specific companies or job titles
- 📍 **Location Intelligence**: Refine searches to specific populated places
- 💾 **Local Database**: Persist dismissed jobs and preferences
- 📊 **Export**: Export filtered results to CSV
- 🛡️ **Stealth**: Uses browser impersonation (curl_cffi) to avoid detection
- 📝 **Logging**: detailed logs for debugging
- 🎯 **API & Web UI**: FastAPI backend with a clean interface

## Installation

1. Clone or download the files to your desired directory
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Method 1: Command Line Interface

Use the main script with command-line arguments:

```bash
# Basic usage
python linkedin_scraper.py --keywords "python developer" --location "New York, NY"

# Advanced usage with multiple filters
python linkedin_scraper.py \
  --keywords "data scientist" \
  --location "San Francisco, CA" \
  --time-range r604800 \
  --job-type F CP \
  --place 2 3 \
  --limit 100 \
  --output my_jobs.csv
```

#### Command Line Arguments

- `--keywords`, `-k`: Job search keywords (e.g., "python developer")
- `--location`, `-l`: Job location (e.g., "New York, NY")
- `--time-range`, `-t`: Time range for job postings
  - `r86400`: Last 24 hours
  - `r604800`: Last week
  - `r2592000`: Last month
- `--distance`, `-d`: Distance in miles (10, 25, 50, 75, 100)
- `--job-type`, `-jt`: Job types (can specify multiple)
  - `F`: Full-time
  - `CP`: Part-time
  - `CC`: Contract
  - `T`: Temporary
  - `CV`: Volunteer
- `--place`, `-p`: Work location (can specify multiple)
  - `1`: On-site
  - `2`: Remote
  - `3`: Hybrid
- `--limit`: Maximum number of jobs to scrape (0 = no limit)
- `--output`, `-o`: Output CSV filename

### Method 2: Configuration File

1. Copy the example configuration:

```bash
cp config_example.py config.py
```

2. Edit `config.py` with your desired settings
3. Run the simple scraper:

```bash
python run_scraper.py
```

## Examples

### Example 1: Remote Python Jobs

```bash
python linkedin_scraper.py \
  --keywords "python developer" \
  --location "Canada" \
  --place 2 \
  --job-type F \
  --limit 50
```

### Example 2: Data Science Jobs in Tech Hubs

```bash
python linkedin_scraper.py \
  --keywords "data scientist machine learning" \
  --location "San Francisco, CA" \
  --time-range r604800 \
  --job-type F CP \
  --distance 25 \
  --limit 100
```

### Example 3: Entry Level Software Engineer

```bash
python linkedin_scraper.py \
  --keywords "software engineer entry level junior" \
  --location "Seattle, WA" \
  --place 1 2 3 \
  --job-type F \
  --output entry_level_jobs.csv
```

## Output

The script generates:

1. **CSV File**: Contains job details with columns:

   - `job_id`: LinkedIn job ID
   - `title`: Job title
   - `company`: Company name
   - `location`: Job location
   - `link`: Direct link to job posting
   - `description`: Job description
   - `posted_time`: When the job was posted
   - `seniority_level`: Required experience level
   - `industry`: Company industry
   - `employment_type`: Full-time, Part-time, etc.
   - `job_function`: Job category/function
   - `scraped_at`: When the data was scraped
2. **Local Database (`dismissed_jobs.db`)**:
   The application uses a SQLite database to maintain state and improve performance:

   - **Dismissed Jobs**: Stores jobs you've marked as uninterested to prevent them from reappearing.
   - **Geo Cache**: Stores mappings from user queries (e.g., "Toronto") to LinkedIn Master GeoIDs and refined Populated Place IDs.
   - **Geo Candidates**: Caches all potential location matches returned by LinkedIn for manual correction.
3. **Log Files** (in `logs/` directory):

   - `error.log`: Error messages
   - `info.log`: Information messages

## Rate Limiting

The script includes built-in rate limiting to avoid being blocked by LinkedIn:

- 0.5 seconds between page requests
- 0.3 seconds between individual job requests

You can adjust these in the script if needed.

## Important Notes

⚠️ **Legal and Ethical Considerations:**

- This script is for educational and personal use only
- Respect LinkedIn's Terms of Service
- Don't overload their servers with too many requests
- Consider the ethical implications of web scraping
- Use the data responsibly

⚠️ **Technical Limitations:**

- LinkedIn may update their website structure, which could break the scraper
- Heavy usage might result in IP blocking
- Some job details might not be available for all postings

## Troubleshooting

### Common Issues:

1. **No jobs found**: Check your search criteria, they might be too restrictive
2. **Rate limiting**: If you get blocked, wait a while and reduce the request frequency
3. **Missing data**: Some fields might be empty if LinkedIn doesn't provide that information
4. **Connection errors**: Check your internet connection and try again

### Debugging:

Check the log files in the `logs/` directory for detailed error messages.

## Contributing

Feel free to improve the script by:

- Adding new search filters
- Improving error handling
- Adding new output formats (JSON, Excel, etc.)
- Enhancing the user interface

## License

This project is for educational purposes. Please respect LinkedIn's Terms of Service and use responsibly.
