#!/usr/bin/env python3
"""
Generate a sample RSS feed for a Tinyview comic.
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_feed(comic_slug: str, days_back: int = 7):
    """Generate RSS feed for a Tinyview comic."""
    scraper = TinyviewScraper()
    
    try:
        # Scrape recent comics
        items = []
        today = datetime.now()
        
        for i in range(days_back):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y/%m/%d")
            
            logger.info(f"Scraping {comic_slug} for {date_str}...")
            result = scraper.scrape_comic(comic_slug, date_str)
            
            if result:
                items.append(result)
                logger.info(f"✅ Found {result['image_count']} images")
            else:
                logger.info(f"❌ No comic found for {date_str}")
        
        if not items:
            logger.error(f"No comics found for {comic_slug}")
            return
        
        # Find comic info
        with open('public/comics_list.json', 'r') as f:
            comics = json.load(f)
        
        comic_info = None
        for comic in comics:
            if comic.get('slug') == comic_slug and comic.get('source') == 'tinyview':
                comic_info = comic
                break
        
        if not comic_info:
            # Fallback
            comic_info = {
                'name': comic_slug.replace('-', ' ').title(),
                'author': 'Unknown',
                'url': f'https://tinyview.com/{comic_slug}',
                'slug': comic_slug
            }
        
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
            feed_path = f"public/feeds/{comic_slug}.xml"
            logger.info(f"\n✅ Feed generated: {feed_path}")
            logger.info(f"Total items: {len(items)}")
        else:
            logger.error(f"\n❌ Failed to generate feed for {comic_slug}")
        
    finally:
        scraper.close_driver()


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Tinyview comic RSS feed')
    parser.add_argument('comic', help='Comic slug (e.g., nick-anderson)')
    parser.add_argument('--days', type=int, default=7, help='Number of days back to scrape')
    
    args = parser.parse_args()
    
    generate_feed(args.comic, args.days)


if __name__ == "__main__":
    main()