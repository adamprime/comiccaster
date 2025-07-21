#!/usr/bin/env python3
"""
Update existing Tinyview feeds with fresh content using parallel processing.
This script updates ALL Tinyview feeds, not just empty ones.
"""

import sys
import os
import json
import logging
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for concurrent processing
MAX_WORKERS = 8  # Same as GoComics
DAYS_TO_SCRAPE = 15  # How many days back to look for comics (increased from 7 to capture more infrequent updates)


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


def scrape_single_comic(comic_slug: str, comic_data: Dict[str, str]) -> Dict:
    """
    Scrape a single comic based on comic data found on the main page.
    
    Args:
        comic_slug: Comic slug identifier
        comic_data: Dict with comic info (href, date, title, url)
        
    Returns:
        Dict with comic data or None if scraping failed
    """
    scraper = TinyviewScraper()
    
    try:
        result = scraper.scrape_comic(comic_slug, comic_data['date'])
        return result
            
    except Exception as e:
        logger.error(f"Error scraping {comic_slug} for {comic_data['date']}: {e}")
        return None
    finally:
        scraper.close_driver()


def update_comic_feed(comic_info: Dict) -> Tuple[bool, str, int]:
    """
    Update RSS feed for a single Tinyview comic using the new smart scraping approach.
    
    Args:
        comic_info: Comic metadata
        
    Returns:
        Tuple of (success, comic_name, items_found)
    """
    try:
        logger.info(f"Updating feed for: {comic_info['name']} ({comic_info['slug']})")
        
        # Use the new scraper method to get recent comics directly
        scraper = TinyviewScraper()
        try:
            # Get all recent comics from the last DAYS_TO_SCRAPE days
            recent_comics = scraper.get_recent_comics(comic_info['slug'], days_back=DAYS_TO_SCRAPE)
            
            if not recent_comics:
                logger.info(f"No recent comics found for {comic_info['name']} in the last {DAYS_TO_SCRAPE} days")
                items = []
            else:
                logger.info(f"Found {len(recent_comics)} recent comics for {comic_info['name']}")
                
                # Now scrape each found comic for full details
                items = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(recent_comics), MAX_WORKERS)) as executor:
                    # Submit scraping tasks for each found comic
                    future_to_comic = {
                        executor.submit(scrape_single_comic, comic_info['slug'], comic_data): comic_data
                        for comic_data in recent_comics
                    }
                    
                    # Process completed futures as they finish
                    for future in concurrent.futures.as_completed(future_to_comic):
                        comic_data = future_to_comic[future]
                        try:
                            result = future.result()
                            if result:
                                items.append(result)
                        except Exception as exc:
                            logger.error(f"{comic_info['name']} comic '{comic_data['title']}' generated an exception: {exc}")
                
                # Items are already sorted by date in get_recent_comics
                logger.info(f"Successfully scraped {len(items)} comics for {comic_info['name']}")
        
        finally:
            scraper.close_driver()
        
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
    """Main function to update all Tinyview feeds with parallel processing."""
    start_time = datetime.now()
    
    logger.info("Starting Tinyview Feed Update")
    logger.info(f"Using {MAX_WORKERS} parallel workers")
    logger.info(f"Scraping {DAYS_TO_SCRAPE} days of history per comic\n")
    
    # Load the comics list
    comics = load_tinyview_comics()
    if not comics:
        logger.error("No comics loaded, exiting")
        return
    
    logger.info(f"Updating {len(comics)} Tinyview comic feeds...")
    
    success_count = 0
    failed_comics = []
    total_items = 0
    comics_with_content = 0
    
    # Process comics in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all comic processing tasks
        future_to_comic = {
            executor.submit(update_comic_feed, comic): comic
            for comic in comics
        }
        
        # Process completed futures as they finish
        completed = 0
        for future in concurrent.futures.as_completed(future_to_comic):
            comic = future_to_comic[future]
            completed += 1
            
            try:
                success, comic_name, items_found = future.result()
                if success:
                    success_count += 1
                    total_items += items_found
                    if items_found > 0:
                        comics_with_content += 1
                    
                    # Progress indicator
                    logger.info(f"Progress: {completed}/{len(comics)} comics processed")
                else:
                    failed_comics.append(comic_name)
            except Exception as exc:
                logger.error(f"{comic['name']} generated an exception: {exc}")
                failed_comics.append(comic['name'])
    
    # Calculate duration
    duration = datetime.now() - start_time
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("FEED UPDATE SUMMARY")
    logger.info("=" * 60)
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
        
        # Copy to main repository if in worktree
        if 'worktrees' in str(Path.cwd()):
            logger.info("\nCopying updated feeds to main repository...")
            os.system('cp -r public/feeds/*.xml ~/coding/rss-comics/public/feeds/')
            logger.info("Feeds copied to main repository for Netlify dev")


if __name__ == "__main__":
    main()