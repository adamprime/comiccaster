"""
Common HTTP client utilities for ComicCaster.
Provides a shared session and common request handling.
"""

import logging
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ComicHTTPClient:
    """Shared HTTP client with retry logic and common headers."""
    
    def __init__(self, base_url: str = "https://www.gocomics.com", max_retries: int = 3):
        self.base_url = base_url
        self.session = self._create_session(max_retries)
    
    def _create_session(self, max_retries: int) -> requests.Session:
        """Create a session with retry logic and common headers."""
        session = requests.Session()
        
        # Set common headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def get(self, url: str, timeout: int = 10, **kwargs) -> Optional[requests.Response]:
        """Make a GET request with error handling."""
        try:
            response = self.session.get(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed for {url}: {e}")
            return None
    
    def get_json(self, url: str, timeout: int = 10, **kwargs) -> Optional[Dict[str, Any]]:
        """Make a GET request and return JSON response."""
        response = self.get(url, timeout, **kwargs)
        if response:
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON from {url}: {e}")
        return None