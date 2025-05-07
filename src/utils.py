from urllib.parse import urlparse
from src.atrip_logger import setup_logger

def is_valid_url(url, domain):
    """Check if the URL is valid, HTTP/HTTPS, and within the specified domain."""
    logger = setup_logger()
    try:
        parsed = urlparse(url)
        # Ensure scheme is HTTP/HTTPS
        if parsed.scheme not in ['http', 'https']:
            logger.debug(f"Invalid scheme for URL {url}: {parsed.scheme}")
            return False
        # Ensure netloc matches domain
        if parsed.netloc != domain:
            logger.debug(f"Domain mismatch for URL {url}: {parsed.netloc} != {domain}")
            return False
        # Basic check for malformed IPv6 or invalid netloc
        if '[' in parsed.netloc and not parsed.netloc.startswith('[') and not parsed.netloc.endswith(']'):
            logger.debug(f"Malformed IPv6 netloc in URL {url}: {parsed.netloc}")
            return False
        return True
    except ValueError as e:
        logger.debug(f"ValueError in URL parsing for {url}: {e}")
        return False

def clean_text(text):
    """Clean text by removing extra whitespace."""
    return ' '.join(text.strip().split()) if text else ''