#!/usr/bin/env python3
"""
Quick generation of Tinyview feeds - generates feeds even if no recent comics found.
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_empty_feed(comic_info):
    """Generate an empty RSS feed for a comic."""
    try:
        # Update comic info for feed generation
        comic_info['url'] = f"https://tinyview.com/{comic_info['slug']}"
        comic_info['source'] = 'tinyview'
        
        # Generate feed with no entries
        feed_gen = ComicFeedGenerator(output_dir='public/feeds')
        
        # Create an empty entry just to have something
        entries = [{
            'title': f"{comic_info['name']} - Coming Soon",
            'link': comic_info['url'],
            'date': datetime.now().strftime('%Y-%m-%d'),
            'description': f"New comics from {comic_info['name']} will appear here when available.",
            'image_url': '',
            'images': []
        }]
        
        # Generate the feed
        success = feed_gen.generate_feed(comic_info, entries)
        
        if success:
            feed_path = f"public/feeds/{comic_info['slug']}.xml"
            logger.info(f"✅ Generated empty feed: {feed_path}")
            return True
        else:
            logger.error(f"❌ Failed to generate feed for {comic_info['name']}")
            return False
            
    except Exception as e:
        logger.error(f"Error generating feed for {comic_info['name']}: {e}")
        return False


def main():
    """Main function to quickly generate all Tinyview feeds."""
    logger.info("Starting Quick Tinyview Feed Generation")
    logger.info("This will generate placeholder feeds for all Tinyview comics\n")
    
    # Load the comics list
    comics_list_path = Path(__file__).parent.parent / 'public' / 'tinyview_comics_list.json'
    
    try:
        with open(comics_list_path, 'r') as f:
            comics = json.load(f)
        logger.info(f"Loaded {len(comics)} Tinyview comics")
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
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
            logger.info(f"✓ {comic['name']}: Feed already exists")
            skipped_count += 1
            continue
            
        if generate_empty_feed(comic):
            success_count += 1
        else:
            failed_comics.append(comic['name'])
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("FEED GENERATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total comics: {len(comics)}")
    logger.info(f"Generated new feeds: {success_count}")
    logger.info(f"Already existed: {skipped_count}")
    logger.info(f"Failed: {len(failed_comics)}")
    
    if failed_comics:
        logger.info("\nFailed comics:")
        for comic in failed_comics:
            logger.info(f"  - {comic}")
    
    # List all existing Tinyview feeds
    logger.info(f"\n{'='*60}")
    logger.info("ALL TINYVIEW FEEDS")
    logger.info(f"{'='*60}")
    
    tinyview_feeds = []
    for comic in comics:
        feed_path = feeds_dir / f"{comic['slug']}.xml"
        if feed_path.exists():
            tinyview_feeds.append(comic['slug'])
    
    logger.info(f"Total Tinyview feeds: {len(tinyview_feeds)}")
    for feed in sorted(tinyview_feeds):
        logger.info(f"  - {feed}")
    
    logger.info(f"\n🎉 All {len(tinyview_feeds)} Tinyview feeds are now available!")
    logger.info("Run 'netlify dev' to view them in the local server.")


if __name__ == "__main__":
    main()