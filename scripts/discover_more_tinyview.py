#!/usr/bin/env python3
"""
Manually discover more Tinyview comics by exploring known patterns.
"""

import sys
import os
import json
import logging
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
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


def check_comic_exists(driver, slug):
    """Check if a comic exists at the given slug."""
    url = f"https://tinyview.com/{slug}"
    logger.info(f"Checking: {url}")
    
    try:
        driver.get(url)
        time.sleep(2)
        
        page_title = driver.title.lower()
        if '404' in page_title or 'not found' in page_title:
            return None
            
        # Get the actual title from the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Look for the comic title
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            title = title_elem.get_text(strip=True)
            # Clean up title
            title = title.replace(' - Tinyview', '').replace(' - TinyView', '').strip()
            if title and title != 'Tinyview' and title != 'TinyView':
                return title
                
        return slug.replace('-', ' ').title()
        
    except Exception as e:
        logger.error(f"Error checking {slug}: {e}")
        return None


def main():
    """Main function to discover more Tinyview comics."""
    # Common comic-related words for URL patterns
    potential_slugs = [
        # Known webcomic creators
        'sarah-andersen', 'sarah-scribbles', 'poorly-drawn-lines',
        'lunarbaboon', 'war-and-peas', 'mr-lovenstein',
        'extra-fabulous', 'invisible-bread', 'loading-artist',
        'awkward-zombie', 'penny-arcade', 'ctrl-alt-del',
        'questionable-content', 'something-positive', 'pvp',
        'girl-genius', 'gunnerkrigg-court', 'order-of-the-stick',
        
        # Political/editorial cartoonists
        'matt-bors', 'jen-sorensen', 'tom-tomorrow',
        'ted-rall', 'matt-wuerker', 'ann-telnaes',
        'mike-luckovich', 'steve-bell', 'patrick-chappatte',
        
        # Daily strip style
        'breaking-cat-news', 'strange-planet', 'false-knees',
        'poorly-drawn-lines', 'web-donuts', 'up-and-out',
        
        # Single panel
        'bizarro', 'speed-bump', 'cornered',
        'free-range', 'reality-check', 'spectickles',
        
        # Tech/geek comics
        'commitstrip', 'monkey-user', 'turnoff-us',
        'geek-and-poke', 'devops-reactions', 'coding-horror',
        
        # More general
        'cats-cafe', 'dog-eat-doug', 'pickles',
        'arctic-circle', 'retail-comic', 'on-the-fastrack'
    ]
    
    driver = setup_driver()
    discovered_comics = []
    
    try:
        # Load existing comics
        with open('public/tinyview_comics_list.json', 'r') as f:
            existing_comics = json.load(f)
        existing_slugs = {comic['slug'] for comic in existing_comics}
        
        logger.info(f"Checking {len(potential_slugs)} potential comic URLs...")
        
        for slug in potential_slugs:
            if slug in existing_slugs:
                logger.info(f"Skipping {slug} - already known")
                continue
                
            title = check_comic_exists(driver, slug)
            if title:
                logger.info(f"✅ Found: {title} at {slug}")
                discovered_comics.append({
                    'name': title,
                    'slug': slug,
                    'url': f'https://tinyview.com/{slug}',
                    'source': 'tinyview',
                    'author': 'Unknown'
                })
            else:
                logger.info(f"❌ Not found: {slug}")
            
            # Be nice to the server
            time.sleep(1)
        
        # Add discovered comics to existing list
        all_comics = existing_comics + discovered_comics
        
        # Save updated list
        with open('public/tinyview_comics_list.json', 'w') as f:
            json.dump(all_comics, f, indent=2)
        
        logger.info(f"\n✅ Discovered {len(discovered_comics)} new comics!")
        logger.info(f"Total Tinyview comics: {len(all_comics)}")
        
        if discovered_comics:
            logger.info("\nNew comics found:")
            for comic in discovered_comics:
                logger.info(f"  - {comic['name']} ({comic['slug']})")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    main()