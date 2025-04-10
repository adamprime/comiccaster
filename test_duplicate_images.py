#!/usr/bin/env python3
"""
Test script to verify that duplicate images are properly filtered out.
"""

import os
import sys
import logging
import feedparser
from datetime import datetime, timedelta
import pytz
from scripts.update_feeds import scrape_comic, load_existing_entries, update_feed

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set timezone to US/Eastern (GoComics timezone)
TIMEZONE = pytz.timezone('US/Eastern')

def test_calvin_and_hobbes_feed():
    """Test the Calvin and Hobbes feed to ensure no duplicate images."""
    logger.info("Testing Calvin and Hobbes feed for duplicate images")
    
    # Create a test comic info
    comic = {
        'name': 'Calvin and Hobbes',
        'author': 'Bill Watterson',
        'url': 'https://www.gocomics.com/calvinandhobbes',
        'slug': 'calvinandhobbes'
    }
    
    # Update the feed
    update_feed(comic)
    
    # Check the feed for duplicate images
    feed_path = os.path.join('feeds', 'calvinandhobbes.xml')
    if not os.path.exists(feed_path):
        logger.error(f"Feed file not found: {feed_path}")
        return False
    
    # Parse the feed
    feed = feedparser.parse(feed_path)
    
    # Check for duplicate dates
    dates = {}
    for entry in feed.entries:
        # Extract date from title
        date_match = None
        for pattern in [r'\d{4}-\d{2}-\d{2}', r'\d{4}/\d{2}/\d{2}']:
            import re
            match = re.search(pattern, entry.title)
            if match:
                date_match = match.group(0)
                break
        
        if not date_match:
            logger.warning(f"Could not extract date from title: {entry.title}")
            continue
        
        # Count entries for this date
        if date_match in dates:
            dates[date_match] += 1
            logger.warning(f"Found duplicate entry for date {date_match}")
        else:
            dates[date_match] = 1
    
    # Check for duplicate images
    image_urls = {}
    for entry in feed.entries:
        # Get image URL from enclosure
        image_url = None
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    image_url = enclosure.get('href', '')
                    break
        
        # If no enclosure, try to extract from description
        if not image_url and hasattr(entry, 'description'):
            import re
            match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
            if match:
                image_url = match.group(1)
        
        if image_url:
            # Check for social media preview images
            if 'GC_Social_FB' in image_url or 'staging-assets' in image_url:
                logger.warning(f"Found social media preview image: {image_url}")
                continue
            
            # Count occurrences of this image URL
            if image_url in image_urls:
                image_urls[image_url] += 1
                logger.warning(f"Found duplicate image URL: {image_url}")
            else:
                image_urls[image_url] = 1
    
    # Report results
    logger.info(f"Feed has {len(feed.entries)} entries")
    logger.info(f"Found {len(dates)} unique dates")
    logger.info(f"Found {len(image_urls)} unique image URLs")
    
    # Check for duplicates
    duplicate_dates = {date: count for date, count in dates.items() if count > 1}
    duplicate_images = {url: count for url, count in image_urls.items() if count > 1}
    
    if duplicate_dates:
        logger.error(f"Found {len(duplicate_dates)} dates with duplicate entries")
        for date, count in duplicate_dates.items():
            logger.error(f"Date {date} has {count} entries")
    else:
        logger.info("No duplicate dates found")
    
    if duplicate_images:
        logger.error(f"Found {len(duplicate_images)} duplicate image URLs")
        for url, count in duplicate_images.items():
            logger.error(f"Image URL {url} appears {count} times")
    else:
        logger.info("No duplicate image URLs found")
    
    return len(duplicate_dates) == 0 and len(duplicate_images) == 0

if __name__ == "__main__":
    success = test_calvin_and_hobbes_feed()
    sys.exit(0 if success else 1) 