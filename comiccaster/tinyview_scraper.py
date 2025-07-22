"""
Tinyview Comic Scraper Module

This module handles fetching and parsing individual comic pages from Tinyview.
It extracts comic images from their CDN and handles both single and multi-image comics.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

# Set up logging
logger = logging.getLogger(__name__)


class TinyviewScraper(BaseScraper):
    """Handles scraping individual comic pages from Tinyview."""
    
    def __init__(self, max_retries: int = 3):
        """Initialize the TinyviewScraper.
        
        Args:
            max_retries: Maximum number of retries for failed requests
        """
        super().__init__(base_url="https://tinyview.com")
        self.driver = None
        self.max_retries = max_retries
    
    def get_source_name(self) -> str:
        """Return the source name for this scraper."""
        return "tinyview"
    
    def setup_driver(self):
        """Set up the Selenium WebDriver with Chrome or Firefox in headless mode."""
        if not self.driver:
            # Try Chrome first (more reliable in CI environments)
            try:
                logger.info("Attempting to set up Chrome WebDriver...")
                chrome_options = Options()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-plugins')
                chrome_options.add_argument('--disable-images')
                chrome_options.add_argument('--disable-web-security')
                chrome_options.add_argument('--allow-running-insecure-content')
                chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.set_window_size(1920, 1080)
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(30)
                logger.info("Chrome WebDriver set up successfully")
                return
                
            except Exception as chrome_error:
                logger.warning(f"Chrome WebDriver failed: {chrome_error}")
                logger.info("Falling back to Firefox WebDriver...")
            
            # Fallback to Firefox if Chrome fails
            try:
                firefox_options = FirefoxOptions()
                firefox_options.add_argument('--headless')
                firefox_options.add_argument('--no-sandbox')
                firefox_options.add_argument('--disable-dev-shm-usage')
                firefox_options.add_argument('--disable-gpu')
                firefox_options.add_argument('--disable-extensions')
                firefox_options.add_argument('--disable-plugins')
                firefox_options.add_argument('--disable-images')
                firefox_options.set_preference("general.useragent.override", 
                    "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0")
                
                # Try to find Firefox binary in common locations
                firefox_paths = [
                    '/usr/bin/firefox',  # Standard apt install
                    '/snap/bin/firefox',  # Snap install
                    'firefox'  # Let system find it
                ]
                
                firefox_binary = None
                for path in firefox_paths:
                    try:
                        import subprocess
                        import os.path
                        if os.path.isfile(path) and os.access(path, os.X_OK):
                            result = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=10)
                            if result.returncode == 0:
                                firefox_binary = path
                                logger.info(f"Found Firefox at: {path}")
                                break
                    except Exception as e:
                        logger.debug(f"Could not verify Firefox at {path}: {e}")
                        continue
                
                # Set binary location if we found a specific path
                if firefox_binary and firefox_binary != 'firefox':
                    firefox_options.binary_location = firefox_binary
                    logger.info(f"Setting Firefox binary location to: {firefox_binary}")
                
                self.driver = webdriver.Firefox(options=firefox_options)
                self.driver.set_window_size(1920, 1080)
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(30)
                logger.info("Firefox WebDriver set up successfully")
                
            except Exception as firefox_error:
                logger.error(f"Firefox WebDriver also failed: {firefox_error}")
                raise Exception(f"Both Chrome and Firefox WebDriver initialization failed. Chrome: {chrome_error}, Firefox: {firefox_error}")
    
    def close_driver(self):
        """Close the Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def get_recent_comics(self, comic_slug: str, days_back: int = 15) -> List[Dict[str, str]]:
        """
        Get all recent comics from the last N days by parsing the comic's main page.
        
        Args:
            comic_slug (str): The slug of the comic to fetch (e.g., 'nick-anderson', 'adhdinos').
            days_back (int): Number of days to look back for recent comics.
            
        Returns:
            List[Dict[str, str]]: List of comic info dictionaries with keys: href, date, title
        """
        comic_main_url = f"{self.base_url}/{comic_slug}"
        
        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                self.setup_driver()
                logger.info(f"Fetching comic main page (attempt {attempt + 1}/{self.max_retries}): {comic_main_url}")
                
                # Navigate to the comic's main page
                self.driver.get(comic_main_url)
                
                # Check for 404 or error pages
                page_title = self.driver.title.lower()
                if '404' in page_title or 'not found' in page_title or 'error' in page_title:
                    logger.warning(f"Comic not found (404) for {comic_main_url}")
                    return []
                
                # Wait for the page to load
                time.sleep(3)
                
                # Parse the page to find all recent comic links
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                all_links = soup.find_all('a', href=True)
                
                # Find all comic links and extract their dates
                recent_comics = []
                cutoff_date = datetime.now() - timedelta(days=days_back)
                
                for link in all_links:
                    href = link['href']
                    
                    # Skip non-comic links
                    if not href.startswith(f'/{comic_slug}/'):
                        continue
                    
                    # Extract date from URL path like /lunarbaboon/2025/07/15/wanted
                    try:
                        parsed = urlparse(urljoin(self.base_url, href))
                        path_parts = parsed.path.strip('/').split('/')
                        
                        # Expected format: ['comic-slug', 'YYYY', 'MM', 'DD', 'title']
                        if len(path_parts) >= 4:
                            comic_name = path_parts[0]
                            if comic_name != comic_slug:
                                continue
                                
                            year_str, month_str, day_str = path_parts[1], path_parts[2], path_parts[3]
                            
                            # Parse the date
                            try:
                                comic_date = datetime(int(year_str), int(month_str), int(day_str))
                                
                                # Only include comics from the last N days
                                if comic_date >= cutoff_date:
                                    title = path_parts[4] if len(path_parts) > 4 else "untitled"
                                    recent_comics.append({
                                        'href': href,
                                        'date': comic_date.strftime('%Y/%m/%d'),
                                        'date_obj': comic_date,
                                        'title': title,
                                        'url': urljoin(self.base_url, href)
                                    })
                                    logger.info(f"Found recent comic: {href} from {comic_date.strftime('%Y-%m-%d')}")
                            except ValueError:
                                # Invalid date format, skip
                                continue
                    except Exception:
                        # Skip invalid URLs
                        continue
                
                # Sort by date (newest first) and return
                recent_comics.sort(key=lambda x: x['date_obj'], reverse=True)
                logger.info(f"Found {len(recent_comics)} recent comics for {comic_slug}")
                
                return recent_comics
                
            except TimeoutException as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} for {comic_main_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff: wait 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {comic_main_url}")
                    return []
                    
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{self.max_retries} for {comic_main_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {comic_main_url}")
                    return []
        
        return []

    def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
        """
        Fetch a specific comic page using Selenium with retry logic and error handling.
        
        Args:
            comic_slug (str): The slug of the comic to fetch (e.g., 'nick-anderson', 'adhdinos').
            date (str): The date in YYYY/MM/DD format.
            
        Returns:
            Optional[str]: The page HTML content, or None if fetching fails.
        """
        # For backward compatibility, we'll use the new method to find the comic
        # and then fetch the specific one that matches the date
        recent_comics = self.get_recent_comics(comic_slug, days_back=30)  # Look back further for specific dates
        
        # Find the comic that matches this date
        target_comic = None
        for comic in recent_comics:
            if comic['date'] == date:
                target_comic = comic
                break
        
        if not target_comic:
            logger.warning(f"No comic found for {comic_slug} on {date}")
            return None
        
        # Fetch the specific comic page
        strip_url = target_comic['url']
        
        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                if not self.driver:
                    self.setup_driver()
                    
                logger.info(f"Fetching comic strip (attempt {attempt + 1}/{self.max_retries}): {strip_url}")
                
                self.driver.get(strip_url)
                
                # Wait for the strip page to load initially
                time.sleep(2)
                
                # Wait for dynamic content to load (panels loaded via JavaScript)
                try:
                    # Wait up to 5 seconds for comic panel container to have images
                    WebDriverWait(self.driver, 5).until(
                        lambda driver: len(driver.find_elements(By.CSS_SELECTOR, 
                            f'img[src*="cdn.tinyview.com/{comic_slug}/{date}"]')) > 0
                    )
                    # Additional wait to ensure all panels are loaded
                    time.sleep(1)
                except:
                    # If wait fails, continue anyway - some comics might not have dynamic loading
                    logger.debug(f"Dynamic content wait timed out for {strip_url}")
                
                # Return the page content
                return self.driver.page_source
                
            except TimeoutException as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} for {strip_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff: wait 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {strip_url}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{self.max_retries} for {strip_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {strip_url}")
                    return None
        
        # This should never be reached, but just in case
        return None
    
    def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
        """
        Extract comic image URLs from the HTML content.
        
        Args:
            html_content (str): The HTML content of the comic page.
            
        Returns:
            List[Dict[str, str]]: List of dictionaries containing image data.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        seen_urls = set()  # Track unique images to avoid duplicates
        
        # Find all images from cdn.tinyview.com
        all_imgs = soup.find_all('img')
        
        for img in all_imgs:
            src = img.get('src', '')
            # Parse URL to check hostname properly (prevent substring matching attacks)
            try:
                parsed_url = urlparse(src)
                if parsed_url.hostname == 'cdn.tinyview.com':
                    # Filter out generic Tinyview images (promotional, UI elements, etc.)
                    path_lower = parsed_url.path.lower()
                    skip_paths = ['/tinyview/app/', '/tinyview/subscribe/', '/tinyview/influence-points/']
                    # Check if path starts with any skip path (more secure than substring matching)
                    if any(path_lower.startswith(skip) for skip in skip_paths):
                        logger.debug(f"Skipping non-comic image: {src}")
                        continue
                    
                    # Check if this looks like a comic image (should contain the comic slug)
                    # Use proper path segment checking instead of substring matching
                    path_segments = parsed_url.path.strip('/').split('/')
                    if comic_slug in path_segments:
                        # Skip profile images and other non-comic images
                        if 'profile' in path_segments or 'external-link' in parsed_url.path:
                            logger.debug(f"Skipping non-comic image: {src}")
                            continue
                        
                        # Check if the image is in a date-based directory
                        # Date format is YYYY/MM/DD
                        date_parts = date.split('/')
                        if len(date_parts) == 3:
                            # Create the date path pattern
                            date_path = f"{comic_slug}/{date}"
                            
                            # Check if the URL contains the date path (more flexible)
                            if date_path in parsed_url.path:
                                # This image is in the correct date directory
                                if src not in seen_urls:
                                    seen_urls.add(src)
                                    image_data = {
                                        'url': src,
                                        'alt': img.get('alt', ''),
                                        'title': img.get('title', '')
                                    }
                                    images.append(image_data)
                                    logger.info(f"Found comic image for date {date}: {src}")
                                else:
                                    logger.debug(f"Skipping duplicate image: {src}")
                            else:
                                logger.debug(f"Image not in date directory {date_path}: {src}")
                        else:
                            logger.debug(f"Invalid date format: {date}")
                    else:
                        logger.debug(f"Skipping image not matching comic slug: {src}")
            except:
                # Skip invalid URLs
                pass
        
        # If no CDN images found, look for other patterns
        if not images:
            # Try data-src attributes (lazy loading)
            for img in all_imgs:
                data_src = img.get('data-src', '')
                if data_src:
                    try:
                        parsed_url = urlparse(data_src)
                        # Check if hostname ends with .tinyview.com or is exactly tinyview.com
                        if parsed_url.hostname and (parsed_url.hostname == 'tinyview.com' or 
                                                    parsed_url.hostname.endswith('.tinyview.com')):
                            # Skip duplicates
                            if data_src not in seen_urls:
                                seen_urls.add(data_src)
                                image_data = {
                                    'url': data_src,
                                    'alt': img.get('alt', ''),
                                    'title': img.get('title', '')
                                }
                                images.append(image_data)
                                logger.info(f"Found comic image (data-src): {data_src}")
                            else:
                                logger.debug(f"Skipping duplicate image (data-src): {data_src}")
                    except:
                        # Skip invalid URLs
                        pass
        
        return images
    
    def extract_metadata(self, html_content: str, comic_slug: str, date: str) -> Dict[str, any]:
        """
        Extract metadata from the comic page.
        
        Args:
            html_content (str): The HTML content of the comic page.
            comic_slug (str): The comic slug.
            date (str): The date string.
            
        Returns:
            Dict[str, any]: Dictionary containing metadata.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        metadata = {
            'comic_slug': comic_slug,
            'date': date,
            'title': '',
            'description': ''
        }
        
        # Try to extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.text.strip()
        
        # Try to extract from meta tags
        og_title = soup.find('meta', property='og:title')
        if og_title:
            metadata['title'] = og_title.get('content', metadata['title'])
        
        og_description = soup.find('meta', property='og:description')
        if og_description:
            metadata['description'] = og_description.get('content', '')
        
        # Look for the Tinyview comic description in the comments div
        comments_div = soup.find('div', class_='comments')
        if comments_div and comments_div.get_text(strip=True):
            description_text = comments_div.get_text(strip=True)
            # Override with this more specific description if found
            metadata['description'] = description_text
            logger.info(f"Found comic description: {description_text[:100]}...")
        
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
        """
        Main method to scrape a comic page and extract its images and metadata.
        
        Args:
            comic_slug (str): The slug of the comic to scrape.
            date (str): The date in YYYY/MM/DD format.
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing the comic data, or None if scraping fails.
        """
        try:
            # Validate input parameters
            if not comic_slug or not date:
                logger.error(f"Invalid parameters: comic_slug='{comic_slug}', date='{date}'")
                return None
            
            # Fetch the comic page
            html_content = self.fetch_comic_page(comic_slug, date)
            if not html_content:
                logger.warning(f"No HTML content retrieved for {comic_slug} on {date}")
                return None
            
            # Extract images
            images = self.extract_images(html_content, comic_slug, date)
            if not images:
                logger.warning(f"No comic images found for {comic_slug} on {date}")
                return None
            
            # Extract metadata
            metadata = self.extract_metadata(html_content, comic_slug, date)
            
            # Get the actual strip URL from the fetch process
            # Since we may have multiple strips, use the comic's main page as the URL
            strip_url = f"{self.base_url}/{comic_slug}/{date}"
            
            # Build the result with all required fields
            result = {
                'source': self.get_source_name(),
                'comic_slug': comic_slug,
                'date': date,
                'title': metadata.get('title', f'{comic_slug} - {date}'),
                'url': strip_url,
                'images': images,
                'image_count': len(images),
                'published_date': metadata.get('published_date', datetime.now()),
                'description': metadata.get('description', '')
            }
            
            # Add convenience fields for single-image comics
            if len(images) == 1:
                result['image_url'] = images[0]['url']
                result['image_alt'] = images[0].get('alt', '')
            
            logger.info(f"Successfully scraped {comic_slug} for {date}: {len(images)} images found")
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error scraping {comic_slug} for {date}: {e}")
            return None
        finally:
            # Ensure driver cleanup happens
            if hasattr(self, '_cleanup_needed'):
                self.close_driver()
    
    def __del__(self):
        """Ensure driver is closed when object is destroyed."""
        self.close_driver()


def main():
    """Main function to demonstrate the TinyviewScraper usage."""
    scraper = TinyviewScraper()
    
    try:
        # Test 1: Nick Anderson (single image comic)
        print("\n=== Testing Nick Anderson (single image) ===")
        today = datetime.now()
        date_str = today.strftime("%Y/%m/%d")
        
        # Try to get today's comic, or a recent one
        result = scraper.scrape_comic('nick-anderson', '2025/01/17')
        if result:
            print(f"\nSuccessfully scraped Nick Anderson comic:")
            print(f"Title: {result.get('title')}")
            print(f"Date: {result.get('date')}")
            print(f"URL: {result.get('url')}")
            print(f"Image count: {result.get('image_count')}")
            if result.get('image_url'):
                print(f"Image URL: {result.get('image_url')}")
        else:
            print("Failed to scrape Nick Anderson comic")
        
        # Test 2: ADHDinos (potentially multiple images)
        print("\n=== Testing ADHDinos (multiple images) ===")
        result = scraper.scrape_comic('adhdinos', '2025/01/15', 'comic-title-here')
        if result:
            print(f"\nSuccessfully scraped ADHDinos comic:")
            print(f"Title: {result.get('title')}")
            print(f"Date: {result.get('date')}")
            print(f"URL: {result.get('url')}")
            print(f"Image count: {result.get('image_count')}")
            for i, img in enumerate(result.get('images', [])):
                print(f"Image {i+1}: {img['url']}")
        else:
            print("Failed to scrape ADHDinos comic")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        scraper.close_driver()


if __name__ == "__main__":
    main()