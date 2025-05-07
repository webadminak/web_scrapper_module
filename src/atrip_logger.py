import logging

def setup_logger():
    logger = logging.getLogger('WebScraper')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler('atrip_scraper.log')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger