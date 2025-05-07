import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from threading import Lock
from src.atrip_logger import setup_logger
from src.utils import is_valid_url, clean_text

try:
    from .crawler import Crawler
except ImportError as e:
    raise ImportError(
        f"Failed to import Crawler from .crawler: {e}. "
        "Ensure this script is run via 'main_sw.py' from the project root (D:/web_scrapper_coventry/), "
        "not directly as 'python src/scrapper.py'. Relative imports require the correct package context."
    )

class WebScraper:
    def __init__(self, start_url, delay=2.0, max_workers=4, timeout=300):
        self.start_url = start_url
        self.delay = delay
        self.max_workers = max_workers
        self.timeout = timeout
        self.data = []
        self.domain = urlparse(start_url).netloc
        self.logger = setup_logger()
        self.image_dir = 'data/images'
        os.makedirs(self.image_dir, exist_ok=True)
        self.json_file = 'data/scraped_data.json'
        self.data_lock = Lock()
        self.load_existing_data()
        self.save_interval = 1
        self.page_count = 0
        self.skipped_duplicates = 0
        self.crawler = Crawler(start_url, delay)

    def load_existing_data(self):
        """Load existing data from JSON file to avoid overwriting."""
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        self.logger.info(f"JSON file {self.json_file} is empty, initializing with empty list")
                        print(f"JSON file {self.json_file} is empty, initializing with empty list")
                        self.data = []
                        return
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                self.logger.info(f"Loaded {len(self.data)} existing pages from {self.json_file}")
                print(f"Loaded {len(self.data)} existing pages from {self.json_file}")
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Error loading JSON from {self.json_file}: {e}. Initializing with empty list.")
                print(f"Error loading JSON from {self.json_file}: {e}. Initializing with empty list and continuing.")
                self.data = []
        else:
            self.logger.info(f"No existing JSON file found at {self.json_file}, starting fresh")
            print(f"No existing JSON file found at {self.json_file}, starting fresh")
            self.data = []

    def download_image(self, img_url):
        """Download an image and return its saved filename with retries."""
        retries = 3
        img_hash = hashlib.md5(img_url.encode()).hexdigest()
        img_extension = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
        img_filename = f"{img_hash}{img_extension}"
        img_path = os.path.join(self.image_dir, img_filename)

        # Check disk space for image directory
        stat = os.statvfs(self.image_dir) if hasattr(os, 'statvfs') else None
        if stat and stat.f_bavail * stat.f_frsize < 1024 * 1024:  # Less than 1MB free
            self.logger.error(f"Insufficient disk space in {self.image_dir} to save image {img_filename}")
            print(f"Error: Insufficient disk space in {self.image_dir} to save image {img_filename}")
            return None

        for attempt in range(retries):
            try:
                self.logger.debug(f"Downloading image {img_url} (Attempt {attempt + 1}/{retries})")
                response = requests.get(img_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                response.raise_for_status()
                
                # Write image file (no lock needed, unique filename ensures safety)
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                self.logger.info(f"Downloaded image: {img_url} -> {img_filename}")
                print(f"Downloaded image: {img_url} -> {img_filename}")
                return img_filename
            except requests.RequestException as e:
                self.logger.error(f"Error downloading image {img_url} (Attempt {attempt + 1}/{retries}): {e}")
                print(f"Error downloading image {img_url} (Attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    self.logger.warning(f"Failed to download image {img_url} after {retries} attempts, skipping")
                    return None
                time.sleep(2 ** attempt)
            except (IOError, OSError) as e:
                self.logger.error(f"Error saving image {img_filename} to {self.image_dir} (Attempt {attempt + 1}/{retries}): {e}")
                print(f"Error saving image {img_filename} to {self.image_dir} (Attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    self.logger.warning(f"Failed to save image {img_filename} after {retries} attempts, skipping")
                    return None
                time.sleep(2 ** attempt)

    def scrape_page(self, url_response_soup):
        """Scrape all visible text content and images from a page."""
        url, response, soup = url_response_soup
        if response is None or soup is None:
            self.logger.warning(f"Skipping scrape for {url} due to fetch error")
            return None

        content_type = response.headers.get('Content-Type', 'unknown')
        status_code = response.status_code
        self.logger.info(f"Response for {url}: Status={status_code}, Content-Type={content_type}")

        if 'text/html' not in content_type.lower():
            self.logger.warning(f"Skipping scrape for {url}: Content-Type is {content_type}, expected text/html")
            return None

        try:
            self.logger.debug(f"Parsing HTML content for {url}")
            for element in soup(['script', 'style']):
                element.decompose()

            title = clean_text(soup.title.string) if soup.title else 'No Title'
            content = clean_text(soup.get_text(separator=' ', strip=True))

            if not content.strip():
                self.logger.warning(f"No visible text content found on {url}, skipping")
                return None

            # Log all img tags found
            img_tags = soup.find_all('img', src=True)
            self.logger.debug(f"Found {len(img_tags)} img tags on {url}")
            for img_tag in img_tags:
                self.logger.debug(f"Img tag src: {img_tag.get('src')}")

            images = []
            for img_tag in img_tags:
                img_url = urljoin(url, img_tag['src'])
                self.logger.debug(f"Processing image URL: {img_url}")
                if is_valid_url(img_url, self.domain):
                    self.logger.debug(f"Image URL {img_url} is valid for domain {self.domain}")
                    img_filename = self.download_image(img_url)
                    if img_filename:
                        images.append({'src': img_url, 'filename': img_filename})
                else:
                    self.logger.debug(f"Image URL {img_url} is not valid for domain {self.domain}, skipping")

            if not images:
                self.logger.info(f"No images were successfully downloaded for {url}")

            page_data = {
                'url': url,
                'title': title,
                'content': content,
                'images': images
            }
            self.logger.info(f"Scraped page data: {page_data}")
            return page_data
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")
            print(f"Error scraping {url}: {e}")
            return None

    def save_to_json(self):
        """Save the scraped data to JSON file with retries and detailed error handling."""
        if not self.data:
            self.logger.warning("No data to save to JSON")
            return

        retries = 3
        for attempt in range(retries):
            try:
                with self.data_lock:
                    self.logger.debug(f"Attempting to save {len(self.data)} pages to {self.json_file} (Attempt {attempt + 1}/{retries})")
                    
                    # Check disk space for the JSON directory
                    json_dir = os.path.dirname(self.json_file) or '.'
                    stat = os.statvfs(json_dir) if hasattr(os, 'statvfs') else None
                    if stat and stat.f_bavail * stat.f_frsize < 1024 * 1024:  # Less than 1MB free
                        self.logger.error(f"Insufficient disk space in {json_dir} to save JSON")
                        print(f"Error: Insufficient disk space in {json_dir} to save JSON")
                        return

                    # Write to a temporary file first, then rename
                    temp_file = self.json_file + '.tmp'
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(self.data, f, ensure_ascii=False, indent=4)
                    
                    os.replace(temp_file, self.json_file)
                    
                    self.logger.info(f"Saved {len(self.data)} pages to {self.json_file}")
                    print(f"Saved {len(self.data)} pages to {self.json_file}")
                    break
            except (IOError, OSError, json.JSONEncodeError) as e:
                self.logger.error(f"Error saving JSON to {self.json_file} (Attempt {attempt + 1}/{retries}): {e}")
                print(f"Error saving JSON to {self.json_file} (Attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    self.logger.error(f"Failed to save JSON after {retries} attempts, giving up")
                    print(f"Error: Failed to save JSON after {retries} attempts, giving up")
                time.sleep(2 ** attempt)

    def run(self):
        """Run the scraper, processing URLs from the crawler in parallel."""
        self.logger.info(f"Starting scrape from {self.start_url} with {self.max_workers} workers (Timeout: {self.timeout}s)")
        start_time = time.time()
        processed_urls = set()
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for url_response_soup in self.crawler.crawl():
                    elapsed_time = time.time() - start_time
                    if elapsed_time > self.timeout:
                        self.logger.warning(f"Scraping process exceeded timeout of {self.timeout}s, stopping")
                        print(f"Scraping process exceeded timeout of {self.timeout}s, stopping")
                        break

                    url = url_response_soup[0]
                    if url in processed_urls:
                        self.skipped_duplicates += 1
                        self.logger.info(f"Skipping already processed URL during scraping: {url}")
                        continue
                    processed_urls.add(url)
                    self.logger.debug(f"Submitting {url} for scraping")
                    page_data = self.scrape_page(url_response_soup)
                    if page_data:
                        with self.data_lock:
                            self.data.append(page_data)
                            self.page_count += 1
                            self.logger.info(f"Appended page data, total pages: {self.page_count}, current data length: {len(self.data)}")
                            self.logger.debug(f"Saving data after scraping {url}")
                            self.save_to_json()
                    else:
                        self.logger.warning(f"No data returned for {url}, skipping append")
        except KeyboardInterrupt:
            self.logger.info("Received KeyboardInterrupt, saving data before exit")
            print("Received KeyboardInterrupt, saving data before exit")
            self.save_to_json()
        except Exception as e:
            self.logger.error(f"Error in scraper run: {e}")
            print(f"Error in scraper run: {e}")
        finally:
            self.logger.info(f"Reached finally block, saving data")
            self.logger.info(f"Scraping complete. Total duplicates skipped during scraping: {self.skipped_duplicates}")
            print(f"Scraping complete. Total duplicates skipped during scraping: {self.skipped_duplicates}")
            self.save_to_json()
        if not self.data:
            self.logger.warning("No data was scraped.")
            print("No data was scraped.")