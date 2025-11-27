#!/usr/bin/env python3
"""
Update TinyView feeds with authenticated scraping using persistent Chrome profile.
Uses a single authenticated browser session for all comics to avoid the 5-comic limit.
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from tinyview_scraper_secure import setup_driver, is_authenticated, load_config_from_env
from comiccaster.tinyview_scraper import TinyviewScraper
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DAYS_TO_SCRAPE = 15  # How many days back to look for comics


def load_tinyview_comics():
    """Load the list of Tinyview comics from the JSON file."""
    comics_list_path = Path(__file__).parent.parent / 'public' / 'tinyview_comics_list.json'
    
    try:
        with open(comics_list_path, 'r') as f:
            comics = json.load(f)
        logger.info(f"Loaded {len(comics)} Tinyview comics")
        return comics
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
        return []


def update_comic_feed(comic_info: Dict, driver) -> Tuple[bool, str, int]:
    """
    Update RSS feed for a single Tinyview comic using an authenticated driver.
    
    Args:
        comic_info: Comic metadata
        driver: Pre-authenticated Selenium WebDriver
        
    Returns:
        Tuple of (success, comic_name, items_found)
    """
    try:
        logger.info(f"Updating feed for: {comic_info['name']} ({comic_info['slug']})")
        
        # Create scraper with the shared authenticated driver
        scraper = TinyviewScraper()
        scraper.driver = driver  # Use the shared authenticated driver
        
        try:
            # Get all recent comics from the last DAYS_TO_SCRAPE days
            recent_comics = scraper.get_recent_comics(comic_info['slug'], days_back=DAYS_TO_SCRAPE)
            
            if not recent_comics:
                logger.info(f"No recent comics found for {comic_info['name']} in the last {DAYS_TO_SCRAPE} days")
                items = []
            else:
                logger.info(f"Found {len(recent_comics)} recent comics for {comic_info['name']}")
                
                # Scrape each found comic for full details (using same driver)
                items = []
                for comic_data in recent_comics:
                    try:
                        result = scraper.scrape_comic(comic_info['slug'], comic_data['date'])
                        if result:
                            items.append(result)
                    except Exception as exc:
                        logger.error(f"{comic_info['name']} comic '{comic_data.get('title', 'unknown')}' generated an exception: {exc}")
                
                logger.info(f"Successfully scraped {len(items)} comics for {comic_info['name']}")
        
        finally:
            # Don't close the driver - we're sharing it!
            pass
        
        # Update comic info for feed generation
        comic_info['url'] = f"https://tinyview.com/{comic_info['slug']}"
        comic_info['source'] = 'tinyview'
        
        # Generate feed
        feed_gen = ComicFeedGenerator(output_dir='public/feeds')
        
        if not items:
            # Create placeholder entry if no comics found
            entries = [{
                'title': f"{comic_info['name']} - No Recent Updates",
                'url': comic_info['url'],
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'description': f"No recent comics found for {comic_info['name']}. Check back later!",
                'image_url': '',
                'images': []
            }]
        else:
            # Convert scraped items to feed entries format
            entries = []
            for item in items:
                entry = {
                    'title': item.get('title', f"{comic_info['name']} - {item['date']}"),
                    'url': item['url'],
                    'pub_date': item['date'].replace('/', '-'),  # Convert to ISO format
                    'description': item.get('description', ''),
                    'image_url': item['images'][0]['url'] if item['images'] else '',
                    'images': item['images']
                }
                entries.append(entry)
        
        # Generate the feed
        success = feed_gen.generate_feed(comic_info, entries)
        
        if success:
            logger.info(f"✅ Updated {comic_info['name']}: {len(items)} items")
            return (True, comic_info['name'], len(items))
        else:
            logger.error(f"❌ Failed to update feed for {comic_info['name']}")
            return (False, comic_info['name'], 0)
            
    except Exception as e:
        logger.error(f"Error updating feed for {comic_info['name']}: {e}")
        return (False, comic_info['name'], 0)


def main():
    """Main function to update all Tinyview feeds using one authenticated session."""
    start_time = datetime.now()
    
    logger.info("Starting Tinyview Feed Update (Authenticated)")
    logger.info("=" * 80)
    
    # Load the comics list
    comics = load_tinyview_comics()
    if not comics:
        logger.error("No comics loaded, exiting")
        return 1
    
    logger.info(f"Updating {len(comics)} Tinyview comic feeds...")
    logger.info(f"Scraping {DAYS_TO_SCRAPE} days of history per comic")
    
    # Setup authenticated driver using persistent Chrome profile
    logger.info("\nSetting up authenticated browser session...")
    driver = setup_driver(show_browser=False, use_profile=True)
    
    try:
        # Check if we're authenticated
        config = load_config_from_env()
        
        logger.info("Checking authentication status...")
        if not is_authenticated(driver, wait_for_auth=True):
            logger.error("❌ Not authenticated!")
            logger.error("\nTo authenticate, run:")
            logger.error("  python3 tinyview_scraper_secure.py --show-browser")
            logger.error("\nThis will log you in and save the session to your Chrome profile.")
            driver.quit()
            return 1
        
        logger.info("✅ Authenticated successfully!")
        logger.info("=" * 80 + "\n")
        
        # Process all comics sequentially (can't use parallel with single driver)
        success_count = 0
        failed_comics = []
        total_items = 0
        comics_with_content = 0
        
        for i, comic in enumerate(comics, 1):
            logger.info(f"\nProgress: {i}/{len(comics)}")
            
            try:
                success, comic_name, items_found = update_comic_feed(comic, driver)
                if success:
                    success_count += 1
                    total_items += items_found
                    if items_found > 0:
                        comics_with_content += 1
                else:
                    failed_comics.append(comic_name)
            except Exception as exc:
                logger.error(f"{comic['name']} generated an exception: {exc}")
                failed_comics.append(comic['name'])
        
        # Calculate duration
        duration = datetime.now() - start_time
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("FEED UPDATE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total comics processed: {len(comics)}")
        logger.info(f"Successfully updated: {success_count}")
        logger.info(f"Failed: {len(failed_comics)}")
        logger.info(f"Comics with content: {comics_with_content}")
        logger.info(f"Total comic items found: {total_items}")
        logger.info(f"Processing time: {duration}")
        
        if failed_comics:
            logger.info("\nFailed comics:")
            for comic in failed_comics:
                logger.info(f"  - {comic}")
        
        if success_count > 0:
            logger.info(f"\n🎉 Successfully updated {success_count} Tinyview feeds!")
            logger.info("The feeds now contain the latest available comics.")
        
        return 0
        
    finally:
        logger.info("\nClosing browser...")
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
