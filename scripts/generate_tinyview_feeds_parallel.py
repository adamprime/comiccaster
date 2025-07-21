#!/usr/bin/env python3
"""
Generate RSS feeds for all Tinyview comics using parallel processing.
Uses the same ThreadPoolExecutor pattern as GoComics with 8 workers.
"""

import sys
import os
import json
import logging
import time
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


def load_tinyview_comics():
    """Load the list of Tinyview comics from the JSON file."""
    comics_list_path = Path(__file__).parent.parent / 'public' / 'tinyview_comics_list.json'
    
    try:
        with open(comics_list_path, 'r') as f:
            comics = json.load(f)
        logger.info(f"Loaded {len(comics)} Tinyview comics from {comics_list_path}")
        return comics
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
        return []


def scrape_comic_for_date(comic_info: Dict, date: datetime) -> Dict:
    """
    Scrape a single comic for a single date.
    
    Args:
        comic_info: Comic metadata
        date: Date to scrape
        
    Returns:
        Dict with comic data or None if scraping failed
    """
    scraper = TinyviewScraper()
    
    try:
        date_str = date.strftime("%Y/%m/%d")
        logger.debug(f"Scraping {comic_info['slug']} for {date_str}")
        
        result = scraper.scrape_comic(comic_info['slug'], date_str)
        
        if result:
            logger.debug(f"✅ Found {result['image_count']} images for {comic_info['slug']} on {date_str}")
            return result
        else:
            logger.debug(f"❌ No comic found for {comic_info['slug']} on {date_str}")
            return None
            
    except Exception as e:
        logger.error(f"Error scraping {comic_info['slug']} for {date}: {e}")
        return None
    finally:
        scraper.close_driver()


def generate_feed_for_comic_parallel(comic_info: Dict, days_back: int = 15) -> Tuple[bool, str]:
    """
    Generate RSS feed for a single Tinyview comic using parallel scraping.
    
    Args:
        comic_info: Comic metadata
        days_back: Number of days to scrape
        
    Returns:
        Tuple of (success, comic_name)
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Generating feed for: {comic_info['name']}")
        logger.info(f"{'='*60}")
        
        # Generate list of dates to scrape
        today = datetime.now()
        target_dates = [today - timedelta(days=i) for i in range(days_back)]
        
        # Use ThreadPoolExecutor for concurrent scraping
        items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all scraping tasks
            future_to_date = {
                executor.submit(scrape_comic_for_date, comic_info, date): date 
                for date in target_dates
            }
            
            # Process completed futures as they finish
            for future in concurrent.futures.as_completed(future_to_date):
                date = future_to_date[future]
                try:
                    result = future.result()
                    if result:
                        items.append(result)
                except Exception as exc:
                    logger.error(f"{comic_info['name']} on {date} generated an exception: {exc}")
        
        if not items:
            logger.warning(f"No comics found for {comic_info['name']}")
            # Generate empty feed
            comic_info['url'] = f"https://tinyview.com/{comic_info['slug']}"
            comic_info['source'] = 'tinyview'
            
            feed_gen = ComicFeedGenerator(output_dir='public/feeds')
            entries = [{
                'title': f"{comic_info['name']} - Coming Soon",
                'link': comic_info['url'],
                'date': datetime.now().strftime('%Y-%m-%d'),
                'description': f"New comics from {comic_info['name']} will appear here when available.",
                'image_url': '',
                'images': []
            }]
            
            success = feed_gen.generate_feed(comic_info, entries)
            return (success, comic_info['name'])
        
        # Sort items by date (newest first)
        items.sort(key=lambda x: x.get('published_date', datetime.now()), reverse=True)
        
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
            return (True, comic_info['name'])
        else:
            logger.error(f"❌ Failed to generate feed for {comic_info['name']}")
            return (False, comic_info['name'])
            
    except Exception as e:
        logger.error(f"Error generating feed for {comic_info['name']}: {e}")
        return (False, comic_info['name'])


def main():
    """Main function to generate all Tinyview feeds with parallel processing."""
    logger.info("Starting Parallel Tinyview Feed Generation")
    logger.info(f"Using {MAX_WORKERS} parallel workers\n")
    
    # Load the comics list
    comics = load_tinyview_comics()
    if not comics:
        logger.error("No comics loaded, exiting")
        return
    
    # Check which feeds already exist
    feeds_dir = Path(__file__).parent.parent / 'public' / 'feeds'
    existing_feeds = set()
    for feed_file in feeds_dir.glob('*.xml'):
        existing_feeds.add(feed_file.stem)
    
    # Determine which comics need processing
    comics_to_process = []
    skipped_count = 0
    
    for comic in comics:
        if comic['slug'] in existing_feeds:
            logger.info(f"✓ {comic['name']}: Feed already exists, skipping")
            skipped_count += 1
        else:
            comics_to_process.append(comic)
    
    if not comics_to_process:
        logger.info("\nAll feeds already exist!")
        return
    
    # Process comics in parallel
    logger.info(f"\nProcessing {len(comics_to_process)} comics in parallel...")
    
    success_count = 0
    failed_comics = []
    
    # Process comics concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all comic processing tasks
        future_to_comic = {
            executor.submit(generate_feed_for_comic_parallel, comic, 15): comic
            for comic in comics_to_process
        }
        
        # Process completed futures as they finish
        for future in concurrent.futures.as_completed(future_to_comic):
            comic = future_to_comic[future]
            try:
                success, comic_name = future.result()
                if success:
                    success_count += 1
                else:
                    failed_comics.append(comic_name)
            except Exception as exc:
                logger.error(f"{comic['name']} generated an exception: {exc}")
                failed_comics.append(comic['name'])
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("FEED GENERATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total comics: {len(comics)}")
    logger.info(f"Generated new feeds: {success_count}")
    logger.info(f"Skipped (already exist): {skipped_count}")
    logger.info(f"Failed: {len(failed_comics)}")
    
    if failed_comics:
        logger.info("\nFailed comics:")
        for comic in failed_comics:
            logger.info(f"  - {comic}")
    
    # List all existing Tinyview feeds
    logger.info(f"\n{'='*60}")
    logger.info("EXISTING TINYVIEW FEEDS")
    logger.info(f"{'='*60}")
    
    tinyview_feeds = []
    for comic in comics:
        feed_path = feeds_dir / f"{comic['slug']}.xml"
        if feed_path.exists():
            tinyview_feeds.append(comic['slug'])
    
    logger.info(f"Found {len(tinyview_feeds)} Tinyview feeds:")
    for feed in sorted(tinyview_feeds):
        logger.info(f"  - {feed}")
    
    if success_count > 0 or len(tinyview_feeds) > 0:
        logger.info(f"\n🎉 Total Tinyview feeds available: {len(tinyview_feeds)}")
        logger.info("You can now run the local server to view them.")


if __name__ == "__main__":
    main()