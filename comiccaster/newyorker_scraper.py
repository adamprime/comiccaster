"""
The New Yorker Daily Cartoon Scraper Module

Scrapes the New Yorker's Daily Cartoon for RSS feed generation.
Uses requests + BeautifulSoup (no authentication required).
Implements rate limiting to be respectful of the site.
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pytz

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class NewYorkerScraper(BaseScraper):
    """Scraper for The New Yorker Daily Cartoon."""
    
    BASE_URL = "https://www.newyorker.com"
    LISTING_URL = "https://www.newyorker.com/cartoons/daily-cartoon"
    
    # Rate limiting: delay between requests (seconds)
    REQUEST_DELAY = 2.5
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """Initialize the New Yorker scraper.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        super().__init__(
            base_url=self.BASE_URL,
            timeout=timeout,
            max_retries=max_retries
        )
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.last_request_time = 0
    
    def get_source_name(self) -> str:
        """Return the source name for this scraper."""
        return 'newyorker'
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.REQUEST_DELAY:
            sleep_time = self.REQUEST_DELAY - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with retry logic and rate limiting.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string, or None on failure
        """
        self._rate_limit()
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Fetching {url} (attempt {attempt + 1}/{self.max_retries})")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None
    
    def get_cartoon_list(self, max_cartoons: int = 15) -> List[Dict[str, str]]:
        """Fetch the list of recent cartoons from the listing page.
        
        Args:
            max_cartoons: Maximum number of cartoons to return
            
        Returns:
            List of dicts with keys: title, url, date_str, author, thumbnail_url
        """
        html = self._fetch_page(self.LISTING_URL)
        if not html:
            logger.error("Failed to fetch cartoon listing page")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        cartoons = []
        
        # Find all cartoon links - they follow the pattern /cartoons/daily-cartoon/...
        # Look for links with cartoon titles
        seen_urls = set()
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Match daily cartoon URLs (but not the main listing page)
            if '/cartoons/daily-cartoon/' in href and href != '/cartoons/daily-cartoon':
                full_url = urljoin(self.BASE_URL, href)
                
                # Skip duplicates
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                
                # Extract title from link text
                title = link.get_text(strip=True)
                
                # Skip empty titles or generic navigation links
                if not title or len(title) < 10:
                    continue
                
                cartoons.append({
                    'title': title,
                    'url': full_url,
                })
                
                if len(cartoons) >= max_cartoons:
                    break
        
        logger.info(f"Found {len(cartoons)} cartoons on listing page")
        return cartoons
    
    def scrape_cartoon_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape an individual cartoon page for full details.
        
        Args:
            url: URL of the cartoon page
            
        Returns:
            Dict with cartoon details, or None on failure
        """
        html = self._fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'url': url,
            'source': 'newyorker',
        }
        
        # Extract high-res image URL
        # Look for the main cartoon image (master/w_1600 quality)
        img_tag = None
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'media.newyorker.com/cartoons/' in src and 'master' in src:
                img_tag = img
                break
        
        if not img_tag:
            # Fallback: look for any cartoon image
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if 'media.newyorker.com/cartoons/' in src:
                    img_tag = img
                    break
        
        if img_tag:
            result['image_url'] = img_tag.get('src', '')
            result['image_alt'] = img_tag.get('alt', '')
        else:
            logger.warning(f"No cartoon image found on {url}")
            return None
        
        # Extract caption (the text below the image, usually in quotes)
        # Search the full page text for quoted caption
        caption = None
        page_text = soup.get_text()
        
        # Look for quoted text that appears before "Cartoon by"
        # Handle both straight quotes and curly quotes (Unicode: U+201C and U+201D)
        caption_match = re.search(r'["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d](?=Cartoon by)', page_text)
        if caption_match:
            caption = f'"{caption_match.group(1)}"'
        
        result['caption'] = caption or ''
        
        # Extract artist name - look for "Cartoon by X" pattern
        artist = None
        page_text = soup.get_text()
        artist_match = re.search(r'Cartoon by ([A-Za-z\s\.]+?)(?:Copy|$|\n)', page_text)
        if artist_match:
            artist = artist_match.group(1).strip()
        
        result['author'] = artist or 'The New Yorker'
        
        # Extract title from page
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove " | The New Yorker" suffix
            title = re.sub(r'\s*\|\s*The New Yorker$', '', title)
            result['title'] = title
        else:
            result['title'] = 'Daily Cartoon'
        
        # Extract date from URL or page content
        # URLs are like: /cartoons/daily-cartoon/friday-december-12th-a-i-slop
        date_match = re.search(r'(\w+)-(\w+)-(\d+)(?:st|nd|rd|th)', url)
        if date_match:
            try:
                day_name, month_str, day = date_match.groups()
                # Parse month
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month = month_map.get(month_str.lower())
                if month:
                    # Assume current year (or previous year if month is ahead)
                    eastern = pytz.timezone('US/Eastern')
                    now = datetime.now(eastern)
                    year = now.year
                    if month > now.month + 1:  # If month is way ahead, it's probably last year
                        year -= 1
                    result['date'] = f"{year}-{month:02d}-{int(day):02d}"
            except (ValueError, AttributeError) as e:
                logger.debug(f"Could not parse date from URL: {e}")
        
        if 'date' not in result:
            # Fallback to today's date
            eastern = pytz.timezone('US/Eastern')
            result['date'] = datetime.now(eastern).strftime('%Y-%m-%d')
        
        # Extract "More Humor and Cartoons" links with full text
        humor_links = []
        for li in soup.find_all('li'):
            link = li.find('a')
            if link and '/humor/' in link.get('href', ''):
                # Get full text and clean up spacing
                full_text = ' '.join(li.get_text().split())  # Normalize whitespace
                href = link.get('href', '')
                humor_links.append({
                    'title': full_text,
                    'url': urljoin(self.BASE_URL, href)
                })
                if len(humor_links) >= 6:
                    break
        
        result['humor_links'] = humor_links
        
        logger.info(f"Scraped cartoon: {result.get('title', 'Unknown')}")
        return result
    
    def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
        """Scrape a comic (implements BaseScraper interface).
        
        For New Yorker, this scrapes all recent cartoons from the listing.
        
        Args:
            comic_slug: Not used for New Yorker (single feed)
            date: Not used for New Yorker (scrapes recent)
            
        Returns:
            Dict with 'cartoons' list containing all scraped cartoons
        """
        cartoons = self.get_cartoon_list(max_cartoons=15)
        
        detailed_cartoons = []
        for cartoon in cartoons:
            details = self.scrape_cartoon_page(cartoon['url'])
            if details:
                detailed_cartoons.append(details)
        
        return {
            'cartoons': detailed_cartoons,
            'scraped_at': datetime.now(pytz.UTC).isoformat()
        }
    
    def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
        """Fetch HTML for a comic page (implements BaseScraper interface)."""
        return self._fetch_page(self.LISTING_URL)
    
    def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
        """Extract comic images from HTML content (implements BaseScraper interface).
        
        Args:
            html_content: The HTML content to parse
            comic_slug: The comic's identifier (not used for New Yorker)
            date: The date string (not used for New Yorker)
            
        Returns:
            List of image dictionaries with url and alt keys
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'media.newyorker.com/cartoons/' in src:
                images.append({
                    'url': src,
                    'alt': img.get('alt', 'New Yorker Cartoon')
                })
        
        return images
