"""
GoComics Scraper Module

This module handles fetching and parsing comic pages from GoComics.
It supports both daily comics and political cartoons, using the enhanced
HTTP scraping approach with JSON-LD structured data.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from .base_scraper import BaseScraper

# Set up logging
logger = logging.getLogger(__name__)


class GoComicsScraper(BaseScraper):
    """Handles scraping comic pages from GoComics.
    
    This scraper supports both regular daily comics and political cartoons
    from GoComics, inheriting from the BaseScraper interface.
    """
    
    def __init__(self, source_type: str = "gocomics-daily"):
        """Initialize the GoComics scraper.
        
        Args:
            source_type: Either "gocomics-daily" or "gocomics-political"
        """
        super().__init__(base_url="https://www.gocomics.com")
        self.source_type = source_type
        self.driver = None
        self.session = requests.Session()
        # Add common headers to mimic a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_source_name(self) -> str:
        """Return the source name for this scraper."""
        return self.source_type
    
    def setup_driver(self):
        """Set up the Selenium WebDriver with Firefox in headless mode."""
        if not self.driver:
            options = Options()
            options.add_argument('-headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.set_preference("general.useragent.override", 
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            self.driver = webdriver.Firefox(options=options)
            self.driver.set_window_size(1920, 1080)
            logger.info("Firefox WebDriver set up successfully")
    
    def close_driver(self):
        """Close the Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
        """Fetch a comic page from GoComics.
        
        Args:
            comic_slug: The comic's slug (e.g., 'garfield')
            date: The date in YYYY/MM/DD format
            
        Returns:
            The HTML content of the page, or None if fetching fails
        """
        url = f"{self.base_url}/{comic_slug}/{date}"
        
        try:
            # Try HTTP-only approach first (faster and more reliable)
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 404:
                logger.warning(f"Comic not found: {url}")
                return None
            else:
                logger.error(f"HTTP error {response.status_code} for {url}")
                # Fall back to Selenium if HTTP fails
                return self._fetch_with_selenium(url)
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            # Fall back to Selenium
            return self._fetch_with_selenium(url)
    
    def _fetch_with_selenium(self, url: str) -> Optional[str]:
        """Fetch a page using Selenium (fallback method)."""
        try:
            self.setup_driver()
            logger.info(f"Fetching {url} with Selenium")
            self.driver.get(url)
            
            # Wait for the comic content to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "picture")))
            
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Selenium fetch failed for {url}: {e}")
            return None
    
    def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
        """Extract comic images from GoComics HTML.
        
        GoComics typically has a single image per comic.
        
        Args:
            html_content: The HTML content to parse
            comic_slug: The comic's slug
            date: The date string
            
        Returns:
            A list with a single image dictionary
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        
        # Try to find the comic image using various methods
        
        # Method 1: Look for the main comic image in a picture element
        picture = soup.find('picture', class_='item-comic-image')
        if picture:
            img = picture.find('img')
            if img and img.get('src'):
                images.append({
                    'url': img['src'],
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
                return images
        
        # Method 2: Look for Open Graph image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            images.append({
                'url': og_image['content'],
                'alt': f"{comic_slug} comic for {date}"
            })
            return images
        
        # Method 3: Look for any img tag with the comic in the src
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'assets.amuniversal.com' in src and comic_slug in src:
                images.append({
                    'url': src,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
                return images
        
        logger.warning(f"No images found for {comic_slug} on {date}")
        return images
    
    def extract_metadata(self, html_content: str, comic_slug: str, date: str) -> Dict[str, Any]:
        """Extract metadata from the comic page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        metadata = {
            'title': '',
            'description': '',
            'author': '',
            'url': f"{self.base_url}/{comic_slug}/{date}"
        }
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.text.strip()
        
        # Try Open Graph tags
        og_title = soup.find('meta', property='og:title')
        if og_title:
            metadata['title'] = og_title.get('content', metadata['title'])
        
        og_description = soup.find('meta', property='og:description')
        if og_description:
            metadata['description'] = og_description.get('content', '')
        
        # Extract author if available
        author_tag = soup.find('meta', {'name': 'author'})
        if author_tag:
            metadata['author'] = author_tag.get('content', '')
        
        # Parse date
        try:
            date_parts = date.split('/')
            if len(date_parts) == 3:
                metadata['published_date'] = datetime(
                    int(date_parts[0]), 
                    int(date_parts[1]), 
                    int(date_parts[2])
                )
        except:
            logger.warning(f"Could not parse date: {date}")
        
        return metadata
    
    def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
        """Scrape a comic from GoComics.
        
        Args:
            comic_slug: The comic's slug (e.g., 'garfield')
            date: The date in YYYY/MM/DD format
            
        Returns:
            Standardized comic data dictionary, or None if scraping fails
        """
        # Fetch the page
        html_content = self.fetch_comic_page(comic_slug, date)
        if not html_content:
            return None
        
        # Extract images
        images = self.extract_images(html_content, comic_slug, date)
        if not images:
            logger.error(f"No images found for {comic_slug} on {date}")
            return None
        
        # Extract metadata
        metadata = self.extract_metadata(html_content, comic_slug, date)
        
        # Build standardized result
        return self.build_comic_result(comic_slug, date, images, metadata)
    
    def __del__(self):
        """Ensure driver is closed when object is destroyed."""
        self.close_driver()


# For backward compatibility, create an alias
ComicScraper = GoComicsScraper