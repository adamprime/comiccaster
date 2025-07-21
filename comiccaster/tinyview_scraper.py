"""
Tinyview Comic Scraper Module

This module handles fetching and parsing individual comic pages from Tinyview.
It extracts comic images from their CDN and handles both single and multi-image comics.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
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
        """
        Fetch a comic page using Selenium with retry logic and error handling.
        
        Args:
            comic_slug (str): The slug of the comic to fetch (e.g., 'nick-anderson', 'adhdinos').
            date (str): The date in YYYY/MM/DD format.
            
        Returns:
            Optional[str]: The page HTML content, or None if fetching fails.
        """
        # First, try to get the comic's main page to find strips for this date
        comic_main_url = f"{self.base_url}/{comic_slug}"
        
        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                self.setup_driver()
                logger.info(f"Fetching comic main page (attempt {attempt + 1}/{self.max_retries}): {comic_main_url}")
                
                # First navigate to the comic's main page
                self.driver.get(comic_main_url)
                
                # Check for 404 or error pages
                page_title = self.driver.title.lower()
                if '404' in page_title or 'not found' in page_title or 'error' in page_title:
                    logger.warning(f"Comic not found (404) for {comic_main_url}")
                    return None
                
                # Wait for the page to load
                time.sleep(3)
                
                # Now we need to find links for the specific date
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Look for links that match the date pattern
                date_links = []
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link['href']
                    # Check if this link contains our date using proper URL parsing
                    try:
                        # Parse the URL and check if the path contains the date
                        parsed = urlparse(urljoin(self.base_url, href))
                        if date in parsed.path:
                            date_links.append(href)
                            logger.info(f"Found link for date {date}: {href}")
                    except Exception:
                        # Skip invalid URLs
                        continue
                
                if not date_links:
                    logger.warning(f"No strips found for date {date} on {comic_slug}")
                    return None
                
                # Visit ALL strips for this date to collect all comics
                all_strips_content = []
                for strip_url in date_links:
                    if not strip_url.startswith('http'):
                        strip_url = urljoin(self.base_url, strip_url)
                    
                    logger.info(f"Fetching strip: {strip_url}")
                    self.driver.get(strip_url)
                    
                    # Save the strip URL for later use
                    self._last_strip_url = strip_url
                    
                    # Wait for the strip page to load
                    time.sleep(2)
                    
                    # Collect the page content
                    all_strips_content.append(self.driver.page_source)
                
                # Combine all strips content into one HTML document
                # This allows us to extract all images from all strips on this date
                combined_html = "<html><body>"
                for content in all_strips_content:
                    soup = BeautifulSoup(content, 'html.parser')
                    body = soup.find('body')
                    if body:
                        combined_html += str(body)
                combined_html += "</body></html>"
                
                logger.info(f"Successfully fetched {len(date_links)} strips for date {date}")
                
                return combined_html
                
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
                    return None
                    
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
                        # Skip profile images
                        if 'profile' in path_segments:
                            logger.debug(f"Skipping profile image: {src}")
                            continue
                        
                        # Include all images from this date (we want all strips from the date)
                        # Check if the URL path contains the date components in order
                        # Date format is YYYY/MM/DD, so split and check if all parts are in the path
                        date_parts = date.split('/')
                        if len(date_parts) == 3:
                            # Check if all date parts appear in the path segments in order
                            path_str = '/'.join(path_segments)
                            date_in_path = all(part in path_segments for part in date_parts)
                            
                            # Also check if the date appears in the expected order in the URL
                            if date_in_path:
                                # Verify the date components appear in sequence
                                try:
                                    year_idx = path_segments.index(date_parts[0])
                                    month_idx = path_segments.index(date_parts[1])
                                    day_idx = path_segments.index(date_parts[2])
                                    if year_idx < month_idx < day_idx:
                                        # Date components are in correct order
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
                                        logger.debug(f"Date components not in expected order: {src}")
                                except ValueError:
                                    logger.debug(f"Date components not all present in path: {src}")
                            else:
                                logger.debug(f"Date components not found in path: {src}")
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