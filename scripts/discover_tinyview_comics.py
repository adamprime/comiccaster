#!/usr/bin/env python3
"""
Discover all available comics on Tinyview.

This script scrapes the Tinyview website to find all available comics
and generates a JSON file with their metadata.
"""

import json
import logging
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
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
    options.add_argument('--disable-gpu')
    options.set_preference("general.useragent.override", 
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1920, 1080)
    logger.info("Firefox WebDriver set up successfully")
    return driver


def discover_comics(driver) -> List[Dict[str, str]]:
    """Discover all comics available on Tinyview."""
    comics = []
    
    # Tinyview homepage or comics list page
    # NOTE: We need to find the actual URL that lists all comics
    # This might be something like https://tinyview.com/comics or similar
    base_url = "https://tinyview.com"
    
    try:
        logger.info(f"Navigating to {base_url}")
        driver.get(base_url)
        
        # Wait for the page to load
        time.sleep(3)
        
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Look for comic links - this pattern will need to be adjusted based on actual HTML structure
        # Common patterns to look for:
        # 1. Links that match /[comic-slug] pattern
        # 2. Links in a comics list or directory
        # 3. Links with specific CSS classes like 'comic-link' or similar
        
        # Try to find all links that might be comics
        all_links = soup.find_all('a', href=True)
        comic_links = []
        
        for link in all_links:
            href = link['href']
            # Parse URL to check if it's a comic page
            if href.startswith('/') and len(href.split('/')) == 2 and not href.startswith('/api'):
                # This looks like a comic URL pattern: /comic-slug
                comic_links.append(link)
            elif 'tinyview.com/' in href and href.count('/') == 3:
                # Full URL pattern: https://tinyview.com/comic-slug
                comic_links.append(link)
        
        logger.info(f"Found {len(comic_links)} potential comic links")
        
        # Process each comic link
        for link in comic_links:
            try:
                href = link['href']
                if not href.startswith('http'):
                    href = urljoin(base_url, href)
                
                # Extract comic slug from URL
                parsed_url = urlparse(href)
                path_parts = parsed_url.path.strip('/').split('/')
                if path_parts and path_parts[0]:
                    comic_slug = path_parts[0]
                    
                    # Get comic name from link text or title
                    comic_name = link.get_text(strip=True) or link.get('title', '') or comic_slug.replace('-', ' ').title()
                    
                    # Skip if this looks like a navigation link
                    if comic_slug in ['about', 'contact', 'privacy', 'terms', 'faq', 'help', 'login', 'signup']:
                        continue
                    
                    comic_info = {
                        'name': comic_name,
                        'slug': comic_slug,
                        'url': f"{base_url}/{comic_slug}",
                        'source': 'tinyview'
                    }
                    
                    # Try to get author info if available
                    author_element = link.find_parent().find(text=lambda t: 'by' in str(t).lower())
                    if author_element:
                        author_text = str(author_element).strip()
                        if 'by' in author_text.lower():
                            author = author_text.split('by')[-1].strip()
                            comic_info['author'] = author
                    
                    # Avoid duplicates
                    if not any(c['slug'] == comic_slug for c in comics):
                        comics.append(comic_info)
                        logger.info(f"Found comic: {comic_name} ({comic_slug})")
                
            except Exception as e:
                logger.warning(f"Error processing link {link}: {e}")
                continue
        
        # If we didn't find comics on the homepage, try common comic listing pages
        if not comics:
            logger.info("No comics found on homepage, trying common listing pages...")
            
            listing_pages = [
                f"{base_url}/comics",
                f"{base_url}/all",
                f"{base_url}/directory",
                f"{base_url}/browse"
            ]
            
            for listing_url in listing_pages:
                try:
                    logger.info(f"Trying {listing_url}")
                    driver.get(listing_url)
                    time.sleep(2)
                    
                    # Check if page exists (not 404)
                    if '404' not in driver.title.lower() and 'not found' not in driver.title.lower():
                        # Parse the page
                        soup = BeautifulSoup(driver.page_source, 'html.parser')
                        # Look for comic links again
                        # ... (repeat the link discovery logic)
                        
                except Exception as e:
                    logger.warning(f"Error accessing {listing_url}: {e}")
                    continue
        
        # Sort comics by name
        comics.sort(key=lambda x: x['name'].lower())
        
    except Exception as e:
        logger.error(f"Error discovering comics: {e}")
    
    return comics


def verify_comic(driver, comic: Dict[str, str]) -> bool:
    """Verify that a comic actually exists by trying to load its page."""
    try:
        # Try to load today's comic
        from datetime import datetime
        today = datetime.now().strftime("%Y/%m/%d")
        test_url = f"{comic['url']}/{today}/cartoon"
        
        logger.info(f"Verifying comic {comic['name']} at {test_url}")
        driver.get(test_url)
        time.sleep(2)
        
        # Check if it's a 404 or error page
        page_title = driver.title.lower()
        if '404' in page_title or 'not found' in page_title or 'error' in page_title:
            logger.warning(f"Comic {comic['name']} returned 404")
            return False
        
        # Check if there are any images from CDN
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        cdn_images = soup.find_all('img', src=lambda x: x and 'cdn.tinyview.com' in x)
        
        if cdn_images:
            logger.info(f"Comic {comic['name']} verified - found {len(cdn_images)} CDN images")
            return True
        else:
            logger.warning(f"Comic {comic['name']} - no CDN images found")
            return False
            
    except Exception as e:
        logger.error(f"Error verifying comic {comic['name']}: {e}")
        return False


def main():
    """Main function to discover and save Tinyview comics."""
    driver = setup_driver()
    
    try:
        # Discover comics
        logger.info("Starting comic discovery...")
        comics = discover_comics(driver)
        
        if not comics:
            logger.warning("No comics discovered automatically. Adding known comics manually...")
            # Add some known comics manually as a fallback
            comics = [
                {
                    'name': 'ADHDinos',
                    'author': 'Dani Donovan',
                    'url': 'https://tinyview.com/adhdinos',
                    'slug': 'adhdinos',
                    'source': 'tinyview'
                },
                {
                    'name': 'Nick Anderson',
                    'author': 'Nick Anderson',
                    'url': 'https://tinyview.com/nick-anderson',
                    'slug': 'nick-anderson',
                    'source': 'tinyview'
                }
            ]
        
        logger.info(f"Total comics found: {len(comics)}")
        
        # Optionally verify each comic (this takes time)
        verify = input("Do you want to verify each comic? This will take some time. (y/n): ")
        if verify.lower() == 'y':
            verified_comics = []
            for comic in comics:
                if verify_comic(driver, comic):
                    verified_comics.append(comic)
                time.sleep(1)  # Be nice to the server
            
            comics = verified_comics
            logger.info(f"Verified comics: {len(comics)}")
        
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
            print(f"  - {comic['name']} by {author} ({comic['slug']})")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()