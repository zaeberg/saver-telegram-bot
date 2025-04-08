import re
from urllib.parse import urlparse
from typing import Tuple, Optional
from utils.logger import logger
from utils.constants import (
    INVALID_URL_MESSAGE,
    UNSUPPORTED_DOMAIN_MESSAGE,
    SUPPORTED_DOMAINS
)

# Validates URL and returns (is_valid, error_message, platform)
# platform will be None if URL is invalid
def validate_url(url: str) -> Tuple[bool, str, Optional[str]]:
    # Basic URL validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        return False, INVALID_URL_MESSAGE, None

    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        if domain.startswith('www.'):
            domain = domain[4:]

        if domain not in SUPPORTED_DOMAINS:
            return False, UNSUPPORTED_DOMAIN_MESSAGE, None

        return True, "", SUPPORTED_DOMAINS[domain]

    except Exception as e:
        logger.error(f"Error parsing URL: {e}")
        return False, INVALID_URL_MESSAGE, None
