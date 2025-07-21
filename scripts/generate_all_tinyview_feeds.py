#!/usr/bin/env python3
"""
Generate RSS feeds for all Tinyview comics.
"""

import sys
import os
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    """Main function to generate all Tinyview feeds."""
    logger.info("Starting Tinyview Feed Generation")
    logger.info("This will generate RSS feeds for all Tinyview comics\n")
    
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
    
    # Generate feeds for all comics
    logger.info(f"\nProcessing {len(comics)} comics...")
    
    success_count = 0
    skipped_count = 0
    failed_comics = []
    
    for comic in comics:
        if comic['slug'] in existing_feeds:
            logger.info(f"✓ {comic['name']}: Feed already exists, skipping")
            skipped_count += 1
            continue
            
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