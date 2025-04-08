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
            
            # First try with simple requests
            response = self.session.get(url)
            if response.status_code == 200 and 'og:image' in response.text:
                return response.text
            
            # If simple request fails, use Selenium
            self.setup_driver()
            logger.info(f"Fetching {url}")
            self.driver.get(url)
            
            # Wait for the comic image to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "meta[property='og:image']")))
            
            # Additional wait for any dynamic content
            time.sleep(2)
            
            return self.driver.page_source
            
        except TimeoutException:
            logger.error(f"Timeout waiting for comic page to load: {url}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch comic page: {e}")
            return None
        finally:
            self.cleanup_driver()
    
    def extract_metadata(self, html_content: str) -> Dict[str, str]:
        """
        Extract metadata from a comic page using Open Graph tags.
        
        Args:
            html_content (str): The HTML content of the comic page.
            
        Returns:
            Dict[str, str]: Dictionary containing the comic metadata.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            metadata = {}
            
            # Extract Open Graph metadata
            og_tags = {
                'image': 'og:image',
                'title': 'og:title',
                'url': 'og:url',
                'description': 'og:description'
            }
            
            for key, tag in og_tags.items():
                meta = soup.find('meta', property=tag)
                if meta:
                    metadata[key] = meta.get('content', '')
            
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