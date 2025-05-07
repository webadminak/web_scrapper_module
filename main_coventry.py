import json
import os
from src.scrapper import WebScraper

def combine_data(all_data, filename='data/scraped_data.json'):
    """Combine data from all crawls into a single JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        print(f"Combined data saved to {filename}")
    except (IOError, json.JSONEncodeError) as e:
        print(f"Error saving combined data to {filename}: {e}")

if __name__ == "__main__":
    # Define your seed links here
    seed_links = [
       "https://www.coventry.gov.uk/downloads/download/1089/coventry_cycle_map_and_guide",
        "https://letstalk.coventry.gov.uk/binleycycleway2",
        "https://www.coventry.gov.uk/cycling-1/ride",
        "https://www.coventry.gov.uk/cyclemap",
        "https://www.coventry.gov.uk/transport-strategy-2/transport-strategy/5",
        "https://letstalk.coventry.gov.uk/binleycycleway",
        "https://www.coventry.gov.uk/cycling-1/segregated-cycleways",
        "https://www.coventry.gov.uk/downloads/download/1089/coventry_cycle_map_and_guide",
    ]

    # Hardcoded delay (seconds between requests per thread)
    delay = 2.0
    max_workers = 4
    timeout = 300  # 5 minutes timeout
    all_data = []

    for url in seed_links:
        print(f"Starting crawl and scrape for seed link: {url}")
        try:
            scraper = WebScraper(
                start_url=url,
                delay=delay,
                max_workers=max_workers,
                timeout=timeout
            )
            scraper.run()
            all_data.extend(scraper.data)
        except Exception as e:
            print(f"Error processing {url}: {e}")

    if all_data:
        combine_data(all_data)
    else:
        print("No data was scraped from any seed links.")