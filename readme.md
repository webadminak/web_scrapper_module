Web Scraper Project
A Python-based web scraper with separate crawling and scraping modules that extracts all text content and images from all reachable pages of given seed links and stores them in JSON format. Supports parallel scraping for faster processing.
Setup

Clone the repository.
Create a virtual environment: python -m venv webscrapper
Activate the virtual environment:
Windows: webscrapper\Scripts\activate
Unix/Linux: source webscrapper/bin/activate


Install dependencies: pip install -r requirements.txt
Create the data/images/ directory.
Add seed links in main.py.
Run the scraper: python main.py

Usage

Update the seed_links list in main.py with your target URLs.
Run main.py to start crawling and scraping all reachable pages.
Output is saved in data/scraped_data.json, and images are saved in data/images/.
Check scraper.log for detailed logs.

Performance Tips

Parallel Scraping: Uses 4 threads by default (max_workers=4 in main.py). Reduce to 2 or increase to 6 based on scraper.log errors (e.g., HTTP 429).
Adjust Delay: Set delay in main.py to 2.0–3.0 seconds. Increase to 5.0 if rate-limiting occurs.
Limit Scope: Add a max_depth parameter in crawler.py to restrict crawling depth (contact developer).
Skip Images: Comment out image downloading in scraper.py to save time.

Troubleshooting

Data not saved to JSON: Check scraper.log for errors like Error saving JSON. Verify disk space (dir data) and permissions (icacls data/scraped_data.json). Increase save_interval in scraper.py to 5 or 10.
Slow crawling: Parallel scraping reduces time, but large sites take minutes to hours. Check scraper.log for page count.
Rate-limiting (HTTP 429): Increase delay to 5.0 or reduce max_workers to 2 in main.py.
No output: Check scraper.log for errors (e.g., timeouts). Verify URLs are accessible and not JavaScript-rendered.
Environment issues: Confirm dependencies (pip list).

Warnings

Parallel scraping increases server load. Monitor scraper.log for HTTP 429 or 403 errors and adjust max_workers or delay to avoid IP bans.
Ensure compliance with the target website’s robots.txt and terms of service.

