"""
Mr. Boffo Scraper Module

Scrapes the Mr. Boffo daily strip (by Joe Martin) for RSS feed generation.
Uses requests + BeautifulSoup (no authentication required).

Mr. Boffo is self-syndicated via Joe Martin's "Neatly Chiseled Features" and
runs on its own site at http://www.mrboffo.com/daily.html. The page is a
hand-built static HTML table (plain HTTP, no HTTPS) that embeds exactly one
comic image — a single <img> whose src lives under ``images/daily/`` (a legacy
fixed path the site overwrites in place each day). There is no per-day
permalink, date metadata, or archive, so the strip is dated by fetch date
(the same "daily dose" model used by The Far Side).
"""

import logging
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class MrBoffoScraper(BaseScraper):
    """Scraper for the Mr. Boffo daily strip."""

    BASE_URL = "http://www.mrboffo.com"
    DAILY_URL = "http://www.mrboffo.com/daily.html"

    # The daily strip image lives under this path fragment; decorative buttons
    # and headers live under images/buttons/ and images/<other> instead.
    IMAGE_PATH_MARKER = "images/daily/"

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """Initialize the Mr. Boffo scraper.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        super().__init__(
            base_url=self.BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        })

    def get_source_name(self) -> str:
        """Return the source name for this scraper."""
        return 'mrboffo'

    def fetch_comic_page(self, comic_slug: str = '', date: str = '') -> Optional[str]:
        """Fetch the daily.html page with retry logic.

        Args:
            comic_slug: Unused (Mr. Boffo is a single comic).
            date: Unused (the page only ever shows the current strip).

        Returns:
            HTML content as a string, or None on failure.
        """
        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Fetching {self.DAILY_URL} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                response = self.session.get(self.DAILY_URL, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        logger.error(
            f"Failed to fetch {self.DAILY_URL} after {self.max_retries} attempts"
        )
        return None

    def extract_images(self, html_content: str, comic_slug: str = '',
                       date: str = '') -> List[Dict[str, str]]:
        """Extract the daily strip image from the page HTML.

        The page contains exactly one comic image (under ``images/daily/``)
        alongside decorative button/header images; this returns only the
        comic image, with its URL absolutized against the site root.

        Args:
            html_content: The HTML content to parse.
            comic_slug: Unused.
            date: Unused.

        Returns:
            A list with the single comic image dict ({'url', 'alt'}), or an
            empty list if no daily-strip image is present.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []

        for img in soup.find_all('img'):
            src = img.get('src', '')
            if self.IMAGE_PATH_MARKER in src:
                images.append({
                    'url': urljoin(self.DAILY_URL, src),
                    'alt': img.get('alt', 'Mr. Boffo'),
                })

        return images

    def scrape_comic(self, comic_slug: str = '', date: str = '') -> Optional[Dict[str, Any]]:
        """Scrape the current Mr. Boffo strip (implements BaseScraper interface).

        Args:
            comic_slug: Unused (single comic).
            date: Unused (the page only shows the current strip).

        Returns:
            A standardized comic result dict (see ``build_comic_result``), or
            None if the page could not be fetched or contained no strip image.
        """
        html = self.fetch_comic_page(comic_slug, date)
        if not html:
            return None

        images = self.extract_images(html, comic_slug, date)
        if not images:
            logger.warning("No daily strip image found on the Mr. Boffo page")
            return None
        if len(images) > 1:
            # The page is expected to carry exactly one daily strip; more than
            # one means the site layout changed and the first match may be the
            # wrong image. Surface it loudly but still publish the first.
            logger.warning(
                f"Expected 1 daily strip image but found {len(images)}; "
                f"using the first ({images[0]['url']})"
            )

        return self.build_comic_result(
            comic_slug or 'mr-boffo',
            date,
            images,
            metadata={'url': self.DAILY_URL, 'title': 'Mr. Boffo'},
        )
