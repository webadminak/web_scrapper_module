import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from collections import deque
import time
import random
from urllib.robotparser import RobotFileParser
from src.atrip_logger import setup_logger
from src.utils import is_valid_url

class Crawler:
    def __init__(self, start_url, delay=2.0, max_pages=100):
        self.start_url = start_url
        self.delay = delay
        self.max_pages = max_pages
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.queue = deque([self.normalize_url(start_url)])
        self.visited.add(self.normalize_url(start_url))
        self.logger = setup_logger()
        self.robots_parser = self._init_robots_parser()
        self.skipped_duplicates = 0
        self.pages_crawled = 0

    def _init_robots_parser(self):
        """Initialize robots.txt parser."""
        parser = RobotFileParser()
        robots_url = f"https://{self.domain}/robots.txt"
        try:
            response = requests.get(robots_url, timeout=5)
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
                self.logger.info(f"Loaded robots.txt from {robots_url}")
            else:
                self.logger.warning(f"Could not fetch robots.txt from {robots_url}, proceeding without restrictions")
        except requests.RequestException as e:
            self.logger.error(f"Error fetching robots.txt: {e}")
            print(f"Error fetching robots.txt: {e}")
        return parser

    def normalize_url(self, url):
        """Normalize URL by removing fragments and ensuring consistent format."""
        parsed = urlparse(url)
        components = (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/'),
            parsed.params,
            parsed.query,
            ''
        )
        return urlunparse(components)

    def can_fetch(self, url):
        """Check if URL is allowed by robots.txt."""
        return self.robots_parser.can_fetch("*", url)

    def get_links(self, url, soup):
        """Extract all valid links from the page."""
        links = []
        normalized_url = self.normalize_url(url)
        self.logger.debug(f"Extracting links from {url}")
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            try:
                if href.startswith(('javascript:', 'mailto:', 'tel:', 'data:', '#')):
                    self.logger.debug(f"Skipping non-HTTP href: {href} on {url}")
                    continue
                full_url = urljoin(url, href)
                normalized_full_url = self.normalize_url(full_url)
                if not is_valid_url(full_url, self.domain):
                    self.logger.debug(f"Skipping URL due to domain mismatch or invalid format: {full_url} (expected domain: {self.domain}) on {url}")
                    continue
                if normalized_full_url in self.visited:
                    self.skipped_duplicates += 1
                    self.logger.info(f"Skipping already visited URL: {normalized_full_url} (found on {url})")
                    continue
                if not self.can_fetch(full_url):
                    self.logger.warning(f"URL blocked by robots.txt: {full_url} on {url}")
                    continue
                links.append(full_url)
                self.visited.add(normalized_full_url)
                self.logger.debug(f"Added new link: {full_url} from {url}")
            except ValueError as e:
                self.logger.error(f"Invalid URL in href '{href}' on {url}: {e}")
                print(f"Invalid URL in href '{href}' on {url}: {e}")
                continue
        self.logger.debug(f"Found {len(links)} new links on {url}")
        return links

    def crawl(self):
        """Crawl all reachable pages, yielding URL and page content."""
        while self.queue and self.pages_crawled < self.max_pages:
            url = self.queue.popleft()
            normalized_url = self.normalize_url(url)
            if normalized_url not in self.visited:
                self.logger.warning(f"URL {url} was in queue but not in visited set, adding to visited")
                self.visited.add(normalized_url)
            self.logger.info(f"Processing URL: {url} (Queue size: {len(self.queue)}, Pages crawled: {self.pages_crawled})")
            retries = 3
            for attempt in range(retries):
                try:
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                    self.logger.debug(f"Sending request to {url} (Attempt {attempt + 1}/{retries})")
                    response = requests.get(url, timeout=5, headers=headers)
                    response.raise_for_status()
                    self.logger.debug(f"Received response from {url}: Status={response.status_code}")
                    soup = BeautifulSoup(response.text, 'html.parser')
                    links = self.get_links(url, soup)
                    for link in links:
                        normalized_link = self.normalize_url(link)
                        if normalized_link not in self.visited:
                            self.queue.append(link)
                            self.visited.add(normalized_link)
                            self.logger.debug(f"Queued new link: {link}")
                        else:
                            self.skipped_duplicates += 1
                            self.logger.info(f"Skipping already queued URL: {normalized_link} (found on {url})")
                    self.logger.info(f"Crawled: {url}, found {len(links)} new links")
                    self.pages_crawled += 1
                    yield url, response, soup
                    break
                except requests.RequestException as e:
                    self.logger.error(f"Error fetching links from {url} (Attempt {attempt + 1}/{retries}): {e}")
                    print(f"Error fetching links from {url} (Attempt {attempt + 1}/{retries}): {e}")
                    if attempt == retries - 1:
                        self.logger.warning(f"Failed to fetch {url} after {retries} attempts, skipping")
                        yield url, None, None
                    time.sleep(2 ** attempt)
            time.sleep(self.delay + random.uniform(0, 0.5))
        self.logger.info(f"Crawling complete. Total pages crawled: {self.pages_crawled}, Total duplicates skipped: {self.skipped_duplicates}")
        print(f"Crawling complete. Total pages crawled: {self.pages_crawled}, Total duplicates skipped: {self.skipped_duplicates}")