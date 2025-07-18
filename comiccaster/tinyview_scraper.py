"""
Tinyview Comic Scraper Module

This module handles fetching and parsing individual comic pages from Tinyview.
It extracts comic images from their CDN and handles both single and multi-image comics.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TinyviewScraper:
    """Handles scraping individual comic pages from Tinyview."""
    
    def __init__(self, base_url: str = "https://tinyview.com"):
        """
        Initialize the TinyviewScraper.
        
        Args:
            base_url (str): The base URL for Tinyview. Defaults to "https://tinyview.com".
        """
        self.base_url = base_url
        self.driver = None
    
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
    
    def fetch_comic_page(self, comic_slug: str, date: str, title_slug: str = "cartoon") -> Optional[str]:
        """
        Fetch a comic page using Selenium to execute JavaScript.
        
        Args:
            comic_slug (str): The slug of the comic to fetch (e.g., 'nick-anderson', 'adhdinos').
            date (str): The date in YYYY/MM/DD format.
            title_slug (str): The title slug (default is 'cartoon' for most comics).
            
        Returns:
            Optional[str]: The page HTML content, or None if fetching fails.
        """
        url = f"{self.base_url}/{comic_slug}/{date}/{title_slug}"
        
        try:
            self.setup_driver()
            logger.info(f"Fetching comic page: {url}")
            self.driver.get(url)
            
            # Wait for the Angular app to load
            time.sleep(3)
            
            # Wait for images from cdn.tinyview.com to load
            logger.info("Waiting for comic images from CDN...")
            wait = WebDriverWait(self.driver, 30)
            
            # Try multiple strategies to find comic images
            comic_found = False
            
            # Strategy 1: Wait for any img with src containing cdn.tinyview.com
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, "//img[contains(@src, 'cdn.tinyview.com')]")))
                comic_found = True
                logger.info("Found CDN images using XPath selector")
            except TimeoutException:
                logger.warning("No CDN images found with XPath selector")
            
            # Strategy 2: Check for images in common container classes
            if not comic_found:
                try:
                    # Common Angular/React container patterns
                    containers = [
                        "comic-container", "comic-wrapper", "comic-image",
                        "story-container", "story-wrapper", "content",
                        "main-content", "comic-strip", "strip-container"
                    ]
                    
                    for container in containers:
                        try:
                            elements = self.driver.find_elements(By.CLASS_NAME, container)
                            if elements:
                                logger.info(f"Found container with class: {container}")
                                # Wait a bit more for images to load within containers
                                time.sleep(2)
                                break
                        except:
                            pass
                            
                except Exception as e:
                    logger.warning(f"Error checking containers: {e}")
            
            # Additional wait to ensure dynamic content is loaded
            time.sleep(2)
            
            return self.driver.page_source
            
        except Exception as e:
            logger.error(f"Failed to fetch comic page: {e}")
            return None
    
    def extract_comic_images(self, html_content: str) -> List[Dict[str, str]]:
        """
        Extract comic image URLs from the HTML content.
        
        Args:
            html_content (str): The HTML content of the comic page.
            
        Returns:
            List[Dict[str, str]]: List of dictionaries containing image data.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        
        # Find all images from cdn.tinyview.com
        all_imgs = soup.find_all('img')
        
        for img in all_imgs:
            src = img.get('src', '')
            if 'cdn.tinyview.com' in src:
                image_data = {
                    'url': src,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                }
                images.append(image_data)
                logger.info(f"Found comic image: {src}")
        
        # If no CDN images found, look for other patterns
        if not images:
            # Try data-src attributes (lazy loading)
            for img in all_imgs:
                data_src = img.get('data-src', '')
                if data_src and ('tinyview' in data_src or 'comic' in data_src):
                    image_data = {
                        'url': data_src,
                        'alt': img.get('alt', ''),
                        'title': img.get('title', '')
                    }
                    images.append(image_data)
                    logger.info(f"Found comic image (data-src): {data_src}")
        
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
    
    def scrape_comic(self, comic_slug: str, date: str, title_slug: str = "cartoon") -> Optional[Dict[str, any]]:
        """
        Main method to scrape a comic page and extract its images and metadata.
        
        Args:
            comic_slug (str): The slug of the comic to scrape.
            date (str): The date in YYYY/MM/DD format.
            title_slug (str): The title slug (default is 'cartoon').
            
        Returns:
            Optional[Dict[str, any]]: Dictionary containing the comic data, or None if scraping fails.
        """
        html_content = self.fetch_comic_page(comic_slug, date, title_slug)
        if not html_content:
            return None
        
        images = self.extract_comic_images(html_content)
        if not images:
            logger.error(f"No comic images found for {comic_slug} on {date}")
            return None
        
        metadata = self.extract_metadata(html_content, comic_slug, date)
        
        # Build the result
        result = {
            **metadata,
            'images': images,
            'image_count': len(images),
            'url': f"{self.base_url}/{comic_slug}/{date}/{title_slug}"
        }
        
        # For single image comics, add convenience fields
        if len(images) == 1:
            result['image_url'] = images[0]['url']
            result['image_alt'] = images[0]['alt']
        
        return result
    
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