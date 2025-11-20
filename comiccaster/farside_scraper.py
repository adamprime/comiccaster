"""
The Far Side Comic Scraper Module

This module handles fetching and parsing comics from The Far Side website.
It supports two types of content:
1. Daily Dose - 5 rotating classic Far Side comics updated daily
2. New Stuff - New digital artwork by Gary Larson (sporadic updates)
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, quote
import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class FarsideScraper(BaseScraper):
    """Scraper for The Far Side comics."""
    
    def __init__(self, source_type='farside-daily', timeout: int = 30, max_retries: int = 3):
        """Initialize the Far Side scraper.
        
        Args:
            source_type: Either 'farside-daily' or 'farside-new'
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        super().__init__(
            base_url="https://www.thefarside.com",
            timeout=timeout,
            max_retries=max_retries
        )
        self.source_type = source_type
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.thefarside.com/'
        })
    
    def get_source_name(self) -> str:
        """Return the source name for this scraper."""
        return self.source_type
    
    def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
        """Scrape comics for a given date.
        
        For Far Side, the date determines which scraping method to use:
        - 'farside-daily' scrapes the 5 daily comics
        - 'farside-new' scrapes new releases
        
        Args:
            comic_slug: The comic slug ('farside-daily' or 'farside-new')
            date: Date in YYYY/MM/DD format
            
        Returns:
            Dictionary with comic data or None if scraping fails
        """
        if self.source_type == 'farside-daily':
            return self.scrape_daily_dose(date)
        elif self.source_type == 'farside-new':
            return self.scrape_new_stuff()
        else:
            logger.error(f"Unknown source type: {self.source_type}")
            return None
    
    def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
        """Fetch HTML content for a Far Side page.
        
        Args:
            comic_slug: The comic slug
            date: Date string (not used for Far Side, but required by interface)
            
        Returns:
            HTML content as string or None
        """
        url = self.base_url if self.source_type == 'farside-daily' else f"{self.base_url}/new-stuff"
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{self.max_retries})")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch page after {self.max_retries} attempts")
                    return None
    
    def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
        """Extract comic images from HTML content.
        
        Args:
            html_content: HTML to parse
            comic_slug: Comic identifier
            date: Date string
            
        Returns:
            List of image dictionaries with 'url' and 'alt' keys
        """
        if self.source_type == 'farside-daily':
            return self._extract_daily_images(html_content)
        elif self.source_type == 'farside-new':
            return self._extract_new_stuff_images(html_content)
        else:
            return []
    
    def scrape_daily_dose(self, date: str) -> Optional[Dict[str, Any]]:
        """Scrape the 5 daily comics from the homepage.
        
        Args:
            date: Date in YYYY/MM/DD format (used for metadata)
            
        Returns:
            Dictionary containing list of 5 comics for the day
        """
        html_content = self.fetch_comic_page('farside-daily', date)
        if not html_content:
            return None
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all divs with data-id (comic containers)
        # Each comic is wrapped in a div.tfs-content__1col with data-id
        comic_containers = soup.find_all('div', attrs={'data-id': True})
        
        if not comic_containers:
            logger.warning("No comic containers found on Daily Dose page")
            return None
        
        comics = []
        for container in comic_containers[:5]:  # Only take first 5
            try:
                comic_data = self._parse_daily_comic(container, date)
                if comic_data:
                    comics.append(comic_data)
            except Exception as e:
                logger.error(f"Error parsing comic container: {e}")
                continue
        
        logger.info(f"Scraped {len(comics)} comics from Daily Dose")
        
        # Return as a composite result
        return {
            'slug': 'farside-daily',
            'date': date.replace('/', '-'),
            'source': 'farside-daily',
            'url': self.base_url,
            'comics': comics,
            'published_date': datetime.now(),
            'title': f"The Far Side - Daily Dose ({date.replace('/', '-')})",
            'image_count': len(comics)
        }
    
    def _parse_daily_comic(self, container: Any, date: str) -> Optional[Dict[str, Any]]:
        """Parse a single Daily Dose comic container.
        
        Args:
            container: BeautifulSoup element for comic container (div.tfs-content__1col)
            date: Date string for metadata
            
        Returns:
            Dictionary with comic data
        """
        # Extract data-id (unique identifier)
        data_id = container.get('data-id')
        if not data_id:
            logger.warning("Comic container missing data-id")
            return None
        
        # Find the inner card
        card = container.find('div', class_='card tfs-comic js-comic')
        if not card:
            logger.warning(f"No card found for comic {data_id}")
            return None
        
        # Find image (lazy-loaded, so it's in data-src)
        img_tag = card.find('img', class_='img-fluid')
        if not img_tag:
            logger.warning(f"No image found for comic {data_id}")
            return None
        
        # Get image URL from data-src (lazy-loaded) or fallback to src
        image_url = img_tag.get('data-src') or img_tag.get('src')
        if not image_url:
            logger.warning(f"No image URL for comic {data_id}")
            return None
        
        # Skip placeholder SVG data URLs
        if image_url.startswith('data:image/svg'):
            logger.warning(f"Got placeholder image for comic {data_id}, trying data-src")
            image_url = img_tag.get('data-src')
            if not image_url:
                return None
        
        # Make sure image URL is absolute
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        elif image_url.startswith('/'):
            image_url = urljoin(self.base_url, image_url)
        elif not image_url.startswith('http'):
            image_url = urljoin(self.base_url, image_url)
        
        # Get caption/alt text
        caption = img_tag.get('alt', '')
        
        # Find figcaption for additional caption text
        figcaption = card.find('figcaption', class_='figure-caption')
        caption_text = ''
        if figcaption:
            caption_text = figcaption.get_text(strip=True)
        
        # Combine captions
        full_caption = caption_text if caption_text else caption
        
        # Transform image URL to use our proxy
        proxied_image_url = self.transform_image_url(image_url)
        
        return {
            'id': data_id,
            'date': date.replace('/', '-'),
            'url': f"{self.base_url}/2025/11/20/{container.get('data-position', '0')}",  # Use permalink
            'image_url': proxied_image_url,
            'original_image_url': image_url,
            'caption': full_caption,
            'title': self._create_title_from_caption(full_caption, data_id)
        }
    
    def scrape_new_stuff(self) -> Optional[Dict[str, Any]]:
        """Scrape new releases from the 'New Stuff' section by navigating through arrows.
        
        The New Stuff page shows one comic at a time with navigation arrows.
        We need to click through to discover all available comics.
        
        Returns:
            Dictionary with new comics or None
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, NoSuchElementException
            
            # Set up headless Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # Start at the New Stuff page
                driver.get(f"{self.base_url}/new-stuff")
                
                # Wait for page to load and possible redirect
                import time
                time.sleep(2)
                
                # Check if we were redirected to a specific comic
                initial_url = driver.current_url
                logger.info(f"Initial URL after loading /new-stuff: {initial_url}")
                
                # If still on /new-stuff (no redirect), try to find a "view" or "enter" button
                if initial_url.endswith('/new-stuff'):
                    logger.info("Page didn't redirect, looking for entry link...")
                    try:
                        # Look for a link or button to enter the New Stuff section
                        entry_link = driver.find_element(By.CSS_SELECTOR, "a[href*='/new-stuff/']")
                        entry_link.click()
                        time.sleep(2)
                        logger.info(f"Clicked entry link, now at: {driver.current_url}")
                    except NoSuchElementException:
                        logger.warning("Could not find entry link to New Stuff comics")
                
                comics = []
                seen_ids = set()
                max_clicks = 50  # Safety limit to prevent infinite loops
                clicks = 0
                
                while clicks < max_clicks:
                    # Get current URL to extract comic ID
                    current_url = driver.current_url
                    match = re.search(r'/new-stuff/(\d+)/([^/]+)', current_url)
                    
                    if match:
                        comic_id = match.group(1)
                        comic_slug = match.group(2)
                        
                        # Only add if we haven't seen this ID
                        if comic_id not in seen_ids:
                            seen_ids.add(comic_id)
                            comics.append({
                                'id': comic_id,
                                'url': current_url,
                                'slug': comic_slug
                            })
                            logger.info(f"Found New Stuff comic {comic_id}: {comic_slug}")
                    
                    # Try to find and click the "next" arrow button
                    # The Far Side uses .js-next class for the next arrow
                    try:
                        # Try The Far Side specific selector first, then fallbacks
                        next_button = None
                        selectors = [
                            ".js-next",  # The Far Side specific
                            "[data-carousel-action*='next']",
                            "button[aria-label*='next']",
                            "button[aria-label*='Next']",
                            "a[aria-label*='next']",
                            "a[aria-label*='Next']",
                            ".next-arrow",
                            ".arrow-next",
                            "button.next"
                        ]
                        
                        for selector in selectors:
                            try:
                                next_button = driver.find_element(By.CSS_SELECTOR, selector)
                                if next_button and next_button.is_displayed():
                                    logger.info(f"Found next button with selector: {selector}")
                                    break
                            except NoSuchElementException:
                                continue
                        
                        if not next_button:
                            logger.info("No more next buttons found, reached end of New Stuff")
                            break
                        
                        # Click the next button
                        next_button.click()
                        
                        # Wait a bit for navigation
                        import time
                        time.sleep(1)
                        
                        # Check if URL changed
                        new_url = driver.current_url
                        if new_url == current_url:
                            logger.info("URL didn't change, likely at the end")
                            break
                        
                    except (NoSuchElementException, TimeoutException) as e:
                        logger.info(f"Reached end of New Stuff comics: {e}")
                        break
                    
                    clicks += 1
                
                logger.info(f"Found {len(comics)} unique New Stuff comics after {clicks} clicks")
                
                return {
                    'slug': 'farside-new',
                    'source': 'farside-new',
                    'url': f"{self.base_url}/new-stuff",
                    'comics': comics,
                    'published_date': datetime.now(),
                    'title': "The Far Side - New Stuff",
                    'image_count': len(comics)
                }
                
            finally:
                driver.quit()
                
        except ImportError:
            logger.error("Selenium is required for New Stuff scraping. Install with: pip install selenium")
            return None
        except Exception as e:
            logger.error(f"Error scraping New Stuff with Selenium: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def scrape_new_stuff_detail(self, comic_url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single New Stuff comic detail page.
        
        Args:
            comic_url: Full URL to the comic page
            
        Returns:
            Dictionary with detailed comic data
        """
        try:
            response = self.session.get(comic_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract comic ID from URL
            match = re.search(r'/new-stuff/(\d+)/', comic_url)
            comic_id = match.group(1) if match else 'unknown'
            
            # Find the main comic image
            # Look for img tags with data-src containing actual image URLs (not data: URIs)
            img_tags = soup.find_all('img')
            image_url = None
            
            for img_tag in img_tags:
                data_src = img_tag.get('data-src', '')
                # Skip placeholder data URIs and find actual image URLs
                if data_src and 'featureassets.amuniversal.com' in data_src:
                    image_url = data_src
                    break
                # Fallback to src if it's a real URL
                src = img_tag.get('src', '')
                if src and not src.startswith('data:') and 'featureassets.amuniversal.com' in src:
                    image_url = src
                    break
            
            if not image_url:
                logger.warning(f"No valid image URL found for {comic_url}")
                return None
            
            # Make absolute URL
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = urljoin(self.base_url, image_url)
            
            # Get title and caption
            title_elem = soup.find('h1') or soup.find('h2')
            title = title_elem.get_text(strip=True) if title_elem else f"Comic {comic_id}"
            
            caption = img_tag.get('alt', '')
            
            # Look for additional text/description
            caption_elem = soup.find('div', class_='card-text') or soup.find('p')
            if caption_elem:
                caption_text = caption_elem.get_text(strip=True)
                if caption_text and len(caption_text) > len(caption):
                    caption = caption_text
            
            proxied_image_url = self.transform_image_url(image_url)
            
            return {
                'id': comic_id,
                'url': comic_url,
                'title': title,
                'image_url': proxied_image_url,
                'original_image_url': image_url,
                'caption': caption
            }
            
        except Exception as e:
            logger.error(f"Error scraping New Stuff detail page {comic_url}: {e}")
            return None
    
    def _extract_daily_images(self, html_content: str) -> List[Dict[str, str]]:
        """Extract images from Daily Dose HTML."""
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        
        comic_cards = soup.find_all('div', class_='card tfs-comic js-comic')
        for card in comic_cards[:5]:
            img_tag = card.find('img', class_='img-fluid')
            if img_tag:
                image_url = img_tag.get('src') or img_tag.get('data-src')
                if image_url:
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = urljoin(self.base_url, image_url)
                    
                    images.append({
                        'url': self.transform_image_url(image_url),
                        'alt': img_tag.get('alt', 'The Far Side comic')
                    })
        
        return images
    
    def _extract_new_stuff_images(self, html_content: str) -> List[Dict[str, str]]:
        """Extract images from New Stuff HTML."""
        # New Stuff requires visiting individual comic pages
        # This method returns empty list; use scrape_new_stuff_detail instead
        return []
    
    def transform_image_url(self, original_url: str) -> str:
        """Transform a Far Side image URL to use our proxy.
        
        Args:
            original_url: Original image URL from The Far Side
            
        Returns:
            Proxied URL that will work in RSS readers
        """
        # URL encode the original URL
        encoded_url = quote(original_url, safe='')
        
        # Return proxy URL
        # Note: This will be relative to the feed domain
        return f"/.netlify/functions/proxy-farside-image?url={encoded_url}"
    
    def _create_title_from_caption(self, caption: str, comic_id: str) -> str:
        """Create a short title from caption text.
        
        Args:
            caption: Full caption text
            comic_id: Comic ID for fallback
            
        Returns:
            Short title (max 60 chars)
        """
        if not caption:
            return f"The Far Side #{comic_id}"
        
        # Take first sentence or first 60 chars
        first_sentence = caption.split('.')[0].strip()
        if len(first_sentence) > 60:
            return first_sentence[:57] + '...'
        return first_sentence if first_sentence else f"The Far Side #{comic_id}"
