"""
Comic Scraper Module

This module handles fetching and parsing individual comic pages from GoComics.
It extracts metadata like the comic image URL, title, and publication date using Open Graph tags.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComicScraper:
    """Handles scraping individual comic pages from GoComics."""
    
    def __init__(self, base_url: str = "https://www.gocomics.com"):
        """
        Initialize the ComicScraper.
        
        Args:
            base_url (str): The base URL for GoComics. Defaults to "https://www.gocomics.com".
        """
        self.base_url = base_url
        self.driver = None
        self.session = requests.Session()
        # Add common headers to mimic a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def setup_driver(self):
        """Set up the Selenium WebDriver with Firefox in headless mode."""
        if not self.driver:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--width=1920")
            options.add_argument("--height=1080")
            
            self.driver = webdriver.Firefox(options=options)
            self.driver.set_window_size(1920, 1080)
    
    def cleanup_driver(self):
        """Clean up the Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def fetch_comic_page(self, comic_slug: str, date: Optional[str] = None) -> Optional[str]:
        """
        Fetch a comic page using Selenium to execute JavaScript.
        
        Args:
            comic_slug (str): The slug of the comic to fetch.
            date (Optional[str]): The date to fetch in YYYY/MM/DD format. If None, fetches the latest.
            
        Returns:
            Optional[str]: The HTML content of the page, or None if the request fails.
        """
        try:
            # Construct the URL
            url = f"{self.base_url}/{comic_slug}"
            if date:
                url = f"{url}/{date}"
            
            # For accurate daily comic detection, we need Selenium to wait for fetchpriority="high" images
            # Skip simple requests and go straight to Selenium for more reliable detection
            self.setup_driver()
            logger.info(f"Fetching {url}")
            self.driver.get(url)
            
            # Wait for the main comic image to load (with responsive srcset)
            wait = WebDriverWait(self.driver, 15)
            
            try:
                # First, wait for any comic image to be present
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[class*='Comic_comic__image']")))
                
                # Additional wait for lazy loading and JavaScript to complete
                time.sleep(3)
                
                # Wait aggressively for the main comic with fetchpriority="high" to load
                # This is the key to getting the actual daily comic vs "best of"
                logger.info("Waiting for main comic with fetchpriority='high' to load...")
                
                # Aggressive polling strategy - check every 2 seconds for up to 30 seconds
                max_wait_time = 30
                poll_interval = 2
                elapsed_time = 0
                
                while elapsed_time < max_wait_time:
                    try:
                        priority_imgs = self.driver.find_elements(By.CSS_SELECTOR, "img[fetchpriority='high']")
                        if priority_imgs:
                            logger.info(f"✅ Found {len(priority_imgs)} fetchpriority='high' comic(s) after {elapsed_time}s")
                            break
                    except:
                        pass
                    
                    logger.info(f"⏳ Still waiting for fetchpriority='high' comic... ({elapsed_time}s elapsed)")
                    time.sleep(poll_interval)
                    elapsed_time += poll_interval
                
                if elapsed_time >= max_wait_time:
                    logger.error("❌ Timeout: No fetchpriority='high' comics found after 30 seconds")
                    
            except TimeoutException:
                logger.warning("No comic images detected, trying og:image fallback")
                # Fallback to og:image detection
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "meta[property='og:image']")))
            
            return self.driver.page_source
            
        except TimeoutException:
            logger.error(f"Timeout waiting for comic page to load: {url}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch comic page: {e}")
            return None
        finally:
            self.cleanup_driver()
    
    def _extract_comic_image(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the actual comic strip image URL from the page.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content.
            
        Returns:
            Optional[str]: The comic strip image URL, or None if not found.
        """
        # Strategy 1: Look for images with comic strip classes
        # Order is important - check for the main comic class FIRST
        comic_strip_selectors = [
            # Main comic image class (the actual daily comic)
            'img.Comic_comic__image__6e_Fw',
            # Strip format comics (often "best of" comics)
            'img.Comic_comic__image_isStrip__eCtT2',
            # Vertical/skinny format comics  
            'img.Comic_comic__image_isSkinny__NZ2aF'
        ]
        
        for selector in comic_strip_selectors:
            comic_imgs = soup.select(selector)
            if comic_imgs:
                # For multiple images, try to find the most relevant one
                best_img = self._select_best_comic_image(comic_imgs, soup)
                if best_img:
                    img_src = best_img.get('src', '')
                    if img_src and 'featureassets.gocomics.com' in img_src:
                        logger.info(f"Found comic using selector: {selector}")
                        return img_src
        
        # Strategy 2: Look for images in comic containers
        comic_containers = soup.find_all(['div', 'section'], 
                                       class_=lambda x: x and any(term in ' '.join(x).lower() 
                                                                 for term in ['comic', 'strip']) if x else False)
        
        for container in comic_containers:
            img = container.find('img')
            if img:
                img_src = img.get('src', '')
                if img_src and 'featureassets.gocomics.com' in img_src:
                    logger.info("Found comic in comic container")
                    return img_src
        
        # Strategy 3: Look for any images from the GoComics asset domain
        all_imgs = soup.find_all('img')
        for img in all_imgs:
            img_src = img.get('src', '')
            if img_src and 'featureassets.gocomics.com' in img_src:
                # Verify it's not a thumbnail or other small image
                if any(size in img_src for size in ['width=2800', 'width=1400', 'large']):
                    logger.info("Found comic using asset domain strategy")
                    return img_src
        
        logger.warning("Could not find comic strip image using any strategy")
        return None
    
    def _select_best_comic_image(self, comic_imgs: list, soup: BeautifulSoup) -> Optional:
        """
        When multiple comic images are found, select the most relevant one.
        
        For Comic_comic__image__6e_Fw class:
        - Look for the image with srcset (indicates main comic with responsive images)
        - Prefer images with fetchpriority="high"
        - Fall back to first image
        
        Args:
            comic_imgs (list): List of comic image elements.
            soup (BeautifulSoup): The full page soup for context.
            
        Returns:
            Optional: The best comic image element, or None.
        """
        if not comic_imgs:
            return None
        
        if len(comic_imgs) == 1:
            return comic_imgs[0]
        
        logger.info(f"Found {len(comic_imgs)} comic images, selecting best one...")
        
        # Strategy 1: Look for images with fetchpriority="high" - THIS IS THE KEY!
        # All actual daily comics have fetchpriority="high", "best of" comics don't
        for img in comic_imgs:
            if img.get('fetchpriority') == 'high':
                logger.info("✅ Selected comic with fetchpriority='high' (the actual daily comic)")
                return img
        
        # Strategy 2: Look for images with srcset (responsive images - backup)
        for img in comic_imgs:
            if img.get('srcset'):
                logger.info("Selected comic with srcset (responsive image)")
                return img
        
        # Strategy 3: Look for images with data-nimg attribute (Next.js optimized images)
        for img in comic_imgs:
            if img.get('data-nimg'):
                logger.info("Selected Next.js optimized image")
                return img
        
        # Fallback: return the first image
        logger.info("Using first comic image as fallback")
        return comic_imgs[0]
    
    def _is_promotional_image(self, image_url: str) -> bool:
        """
        Check if an image URL appears to be a promotional/social media image rather than a comic strip.
        
        Args:
            image_url (str): The image URL to check.
            
        Returns:
            bool: True if the image appears to be promotional, False otherwise.
        """
        if not image_url:
            return True
            
        # Check for social media image patterns
        social_indicators = [
            'GC_Social_FB_',  # Facebook social images
            'GC_Social_',     # General social images
            'social_',        # Social media images
            '_social',        # Social media images
            'promotional',    # Promotional images
            'banner',         # Banner images
        ]
        
        for indicator in social_indicators:
            if indicator in image_url:
                logger.warning(f"Detected promotional image: {indicator} in {image_url}")
                return True
        
        # Check for asset domain vs social asset domain
        if 'gocomicscmsassets.gocomics.com' in image_url:
            logger.warning(f"Detected CMS asset (likely promotional): {image_url}")
            return True
            
        return False
    
    def extract_metadata(self, html_content: str) -> Dict[str, str]:
        """
        Extract metadata from a comic page, prioritizing actual comic strip images over og:image.
        
        Args:
            html_content (str): The HTML content of the comic page.
            
        Returns:
            Dict[str, str]: Dictionary containing the comic metadata.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            metadata = {}
            
            # Extract Open Graph metadata (for title, url, description)
            og_tags = {
                'title': 'og:title',
                'url': 'og:url',
                'description': 'og:description'
            }
            
            for key, tag in og_tags.items():
                meta = soup.find('meta', property=tag)
                if meta:
                    metadata[key] = meta.get('content', '')
            
            # Extract the actual comic strip image (prioritized over og:image)
            comic_image_url = self._extract_comic_image(soup)
            if comic_image_url and not self._is_promotional_image(comic_image_url):
                metadata['image'] = comic_image_url
                logger.info(f"Found valid comic strip image: {comic_image_url}")
            else:
                # Fallback to og:image if no comic strip image found
                og_image = soup.find('meta', property='og:image')
                if og_image:
                    og_image_url = og_image.get('content', '')
                    if self._is_promotional_image(og_image_url):
                        logger.error(f"Both comic strip and og:image appear to be promotional. Using og:image anyway: {og_image_url}")
                    metadata['image'] = og_image_url
                    logger.warning("Using og:image as fallback - may not be the actual comic strip")
                else:
                    logger.error("No image found at all")
            
            # Extract publication date
            date_meta = soup.find('meta', property='article:published_time')
            if date_meta:
                pub_date = date_meta.get('content', '')
                try:
                    # Convert to RFC 2822 format for RSS
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    metadata['pub_date'] = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
                except ValueError:
                    logger.warning(f"Could not parse publication date: {pub_date}")
                    metadata['pub_date'] = ''
            
            # Make image URL absolute if it's relative
            if 'image' in metadata and metadata['image'].startswith('/'):
                metadata['image'] = urljoin(self.base_url, metadata['image'])
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            raise
    
    def scrape_comic(self, comic_slug: str, date: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Main method to scrape a comic page and extract its metadata.
        
        Args:
            comic_slug (str): The slug of the comic to scrape.
            date (Optional[str]): The date to scrape in YYYY/MM/DD format. If None, scrapes the latest.
            
        Returns:
            Optional[Dict[str, str]]: Dictionary containing the comic metadata, or None if scraping fails.
        """
        html_content = self.fetch_comic_page(comic_slug, date)
        if not html_content:
            return None
        
        return self.extract_metadata(html_content)

def main():
    """Main function to demonstrate the ComicScraper usage."""
    try:
        scraper = ComicScraper()
        
        # Example: Scrape today's Garfield comic
        metadata = scraper.scrape_comic('garfield')
        if metadata:
            print("\nSuccessfully scraped comic:")
            for key, value in metadata.items():
                print(f"{key}: {value}")
        
    except Exception as e:
        logger.error(f"Failed to scrape comic: {e}")
        raise

if __name__ == "__main__":
    main() 