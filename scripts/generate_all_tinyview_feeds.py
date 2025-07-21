#!/usr/bin/env python3
"""
Discover all Tinyview comics and generate RSS feeds for them.
"""

import sys
import os
import json
import logging
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from comiccaster.tinyview_scraper import TinyviewScraper
from comiccaster.feed_generator import ComicFeedGenerator

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


def discover_all_tinyview_comics(driver):
    """Discover all comics from Tinyview by exploring the site."""
    comics = []
    
    # Start with known comics
    known_comics = [
        {'name': 'ADHDinos', 'slug': 'adhdinos', 'author': 'Pina Vazquez'},
        {'name': 'Nick Anderson', 'slug': 'nick-anderson', 'author': 'Nick Anderson'},
        {'name': 'Fowl Language', 'slug': 'fowl-language', 'author': 'Brian Gordon'},
    ]
    
    # Try to discover more from the homepage
    logger.info("Exploring Tinyview homepage for comics...")
    driver.get("https://tinyview.com")
    time.sleep(5)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Look for comic links
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.startswith('/') and '/' not in href[1:]:  # Single-segment paths
            slug = href.strip('/')
            
            # Skip known non-comic pages
            skip_slugs = ['tinyview', 'about', 'contact', 'privacy', 'terms', 'help', 
                         'login', 'signup', 'subscribe', 'api', 'admin', 'support',
                         'comic-series-directory', 'directory', 'browse', 'home']
            
            if slug in skip_slugs:
                continue
            
            # Check if we already have this comic
            if not any(c['slug'] == slug for c in known_comics):
                name = link.get_text(strip=True) or slug.replace('-', ' ').title()
                logger.info(f"Found potential comic: {name} ({slug})")
                
                # Verify it's a real comic page
                comic_url = f"https://tinyview.com/{slug}"
                driver.get(comic_url)
                time.sleep(2)
                
                page_title = driver.title.lower()
                if '404' not in page_title and 'not found' not in page_title:
                    known_comics.append({
                        'name': name,
                        'slug': slug,
                        'author': 'Unknown'
                    })
    
    # Also try the directory page one more time
    logger.info("Checking directory page...")
    driver.get("https://tinyview.com/tinyview/comic-series-directory")
    time.sleep(5)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text(strip=True)
        
        if href.startswith('/') and text and '/' not in href[1:]:
            slug = href.strip('/')
            if not any(c['slug'] == slug for c in known_comics):
                if slug not in skip_slugs:
                    known_comics.append({
                        'name': text,
                        'slug': slug,
                        'author': 'Unknown'
                    })
                    logger.info(f"Found from directory: {text} ({slug})")
    
    return known_comics


def generate_feed_for_comic(comic_info, days_back=7):
    """Generate RSS feed for a single Tinyview comic."""
    scraper = TinyviewScraper()
    
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Generating feed for: {comic_info['name']}")
        logger.info(f"{'='*60}")
        
        # Scrape recent comics
        items = []
        today = datetime.now()
        
        for i in range(days_back):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y/%m/%d")
            
            logger.info(f"Scraping {comic_info['slug']} for {date_str}...")
            result = scraper.scrape_comic(comic_info['slug'], date_str)
            
            if result:
                items.append(result)
                logger.info(f"✅ Found {result['image_count']} images")
            else:
                logger.info(f"❌ No comic found for {date_str}")
        
        if not items:
            logger.warning(f"No comics found for {comic_info['name']}")
            return False
        
        # Update comic info for feed generation
        comic_info['url'] = f"https://tinyview.com/{comic_info['slug']}"
        comic_info['source'] = 'tinyview'
        
        # Generate feed
        feed_gen = ComicFeedGenerator(output_dir='public/feeds')
        
        # Convert scraped items to feed entries format
        entries = []
        for item in items:
            entry = {
                'title': item.get('title', f"{comic_info['name']} - {item['date']}"),
                'link': item['url'],
                'date': item['date'].replace('/', '-'),  # Convert to ISO format
                'description': item.get('description', ''),
                'image_url': item['images'][0]['url'] if item['images'] else '',
                'images': item['images']
            }
            entries.append(entry)
        
        # Generate the feed
        success = feed_gen.generate_feed(comic_info, entries)
        
        if success:
            feed_path = f"public/feeds/{comic_info['slug']}.xml"
            logger.info(f"✅ Feed generated: {feed_path}")
            logger.info(f"Total items: {len(items)}")
            return True
        else:
            logger.error(f"❌ Failed to generate feed for {comic_info['name']}")
            return False
            
    except Exception as e:
        logger.error(f"Error generating feed for {comic_info['name']}: {e}")
        return False
    finally:
        scraper.close_driver()


def main():
    """Main function to discover and generate all Tinyview feeds."""
    logger.info("Starting Tinyview Feed Generation")
    logger.info("This will discover all comics and generate RSS feeds\n")
    
    # First, discover all comics
    driver = setup_driver()
    
    try:
        comics = discover_all_tinyview_comics(driver)
        logger.info(f"\nDiscovered {len(comics)} comics total")
        
        # Save the discovered comics
        with open('public/tinyview_comics_list.json', 'w') as f:
            json.dump(comics, f, indent=2)
        logger.info("Saved comic list to public/tinyview_comics_list.json")
        
    finally:
        driver.quit()
    
    # Generate feeds for all comics
    logger.info(f"\nGenerating feeds for {len(comics)} comics...")
    
    success_count = 0
    failed_comics = []
    
    for comic in comics:
        if generate_feed_for_comic(comic, days_back=5):
            success_count += 1
        else:
            failed_comics.append(comic['name'])
        
        # Small delay between comics to be nice to the server
        time.sleep(2)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("FEED GENERATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total comics: {len(comics)}")
    logger.info(f"Successful feeds: {success_count}")
    logger.info(f"Failed feeds: {len(failed_comics)}")
    
    if failed_comics:
        logger.info("\nFailed comics:")
        for comic in failed_comics:
            logger.info(f"  - {comic}")
    
    if success_count > 0:
        logger.info(f"\n🎉 Successfully generated {success_count} Tinyview feeds!")
        logger.info("You can now run the local server to view them.")
    
    # Update the main comics list
    update_main_comics_list(comics)


def update_main_comics_list(tinyview_comics):
    """Add Tinyview comics to the main comics list."""
    try:
        with open('public/comics_list.json', 'r') as f:
            all_comics = json.load(f)
        
        # Find the highest position
        max_position = max(comic.get('position', 0) for comic in all_comics)
        
        # Add Tinyview comics that aren't already in the list
        added_count = 0
        for comic in tinyview_comics:
            if not any(c.get('slug') == comic['slug'] and c.get('source') == 'tinyview' for c in all_comics):
                max_position += 1
                all_comics.append({
                    'name': comic['name'],
                    'author': comic.get('author', 'Unknown'),
                    'url': f"https://tinyview.com/{comic['slug']}",
                    'slug': comic['slug'],
                    'position': max_position,
                    'is_updated': False,
                    'source': 'tinyview'
                })
                added_count += 1
        
        # Save updated list
        with open('public/comics_list.json', 'w') as f:
            json.dump(all_comics, f, indent=2)
        
        logger.info(f"\nAdded {added_count} new Tinyview comics to main comics list")
        
    except Exception as e:
        logger.error(f"Error updating main comics list: {e}")


if __name__ == "__main__":
    main()