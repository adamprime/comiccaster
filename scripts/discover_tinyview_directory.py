#!/usr/bin/env python3
"""
Discover all available comics from Tinyview's comic series directory.

This script scrapes https://tinyview.com/tinyview/comic-series-directory
to find all available comics and generates a JSON file with their metadata.
"""

import json
import logging
import time
from typing import List, Dict
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_driver():
    """Set up the Selenium WebDriver with Firefox in headless mode."""
    options = Options()
    options.add_argument('-headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1920, 1080)
    logger.info("Firefox WebDriver set up successfully")
    return driver


def discover_comics_from_directory(driver) -> List[Dict[str, str]]:
    """Discover all comics from the Tinyview directory page."""
    comics = []
    directory_url = "https://tinyview.com/tinyview/comic-series-directory"
    
    try:
        logger.info(f"Navigating to directory: {directory_url}")
        driver.get(directory_url)
        
        # Wait for the page to load
        time.sleep(5)  # Give Angular/React time to render
        
        # Wait for comic links to appear
        try:
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "a")))
        except:
            logger.warning("Timeout waiting for links to load")
        
        # Get page source and parse
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all links that point to comic pages
        all_links = soup.find_all('a', href=True)
        logger.info(f"Found {len(all_links)} total links on directory page")
        
        for link in all_links:
            href = link['href']
            text = link.get_text(strip=True)
            
            # Skip empty links and navigation
            if not href or not text:
                continue
                
            # Parse the URL
            if not href.startswith('http'):
                href = urljoin("https://tinyview.com", href)
            
            parsed_url = urlparse(href)
            
            # Check if this looks like a comic page
            # Pattern: https://tinyview.com/comic-slug
            path_parts = parsed_url.path.strip('/').split('/')
            
            # Skip if it's not a direct comic link
            if parsed_url.hostname != 'tinyview.com' or len(path_parts) != 1:
                continue
            
            comic_slug = path_parts[0]
            
            # Skip common non-comic pages
            skip_slugs = ['tinyview', 'about', 'contact', 'privacy', 'terms', 'help', 
                         'login', 'signup', 'subscribe', 'api', 'admin', 'support',
                         'comic-series-directory', 'directory', 'browse']
            
            if comic_slug in skip_slugs:
                continue
            
            # Look for author info if available
            author = ""
            # Try to find author in parent elements
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                if ' by ' in parent_text:
                    author = parent_text.split(' by ')[-1].strip()
            
            comic_info = {
                'name': text,
                'slug': comic_slug,
                'url': f"https://tinyview.com/{comic_slug}",
                'source': 'tinyview'
            }
            
            if author:
                comic_info['author'] = author
            
            # Avoid duplicates
            if not any(c['slug'] == comic_slug for c in comics):
                comics.append(comic_info)
                logger.info(f"Found comic: {text} ({comic_slug})")
        
        # Sort by name
        comics.sort(key=lambda x: x['name'].lower())
        
    except Exception as e:
        logger.error(f"Error discovering comics: {e}")
        import traceback
        traceback.print_exc()
    
    return comics


def main():
    """Main function to discover and save Tinyview comics."""
    driver = setup_driver()
    
    try:
        # Discover comics from directory
        logger.info("Starting comic discovery from directory...")
        comics = discover_comics_from_directory(driver)
        
        logger.info(f"Total comics found: {len(comics)}")
        
        # Save to JSON file
        output_file = "public/tinyview_comics_list.json"
        with open(output_file, 'w') as f:
            json.dump(comics, f, indent=2)
        
        logger.info(f"Saved {len(comics)} comics to {output_file}")
        
        # Print summary
        print("\n=== Comic Discovery Summary ===")
        print(f"Total comics found: {len(comics)}")
        print("\nComics:")
        for comic in comics:
            author = comic.get('author', 'Unknown')
            print(f"  - {comic['name']} ({comic['slug']})")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()