#!/usr/bin/env python3
"""
Script to regenerate the Adam@Home feed with our updated comic scraper
"""

import sys
import logging
from datetime import datetime, timedelta
import pytz
from scripts.update_feeds import scrape_comic, regenerate_feed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set timezone to US/Eastern (GoComics timezone)
TIMEZONE = pytz.timezone('US/Eastern')

def main():
    # Comic info
    comic_info = {
        'name': 'Adam@Home',
        'slug': 'adamathome',
        'url': 'https://www.gocomics.com/adamathome'
    }
    
    # Collect entries for the past 5 days
    entries = []
    current_date = datetime.now(TIMEZONE)
    
    for day in range(5, 10):
        # Create the proper date object for this comic strip
        target_date = datetime(2025, 4, day, tzinfo=TIMEZONE)
        url = f'https://www.gocomics.com/adamathome/2025/04/{day:02d}'
        logger.info(f"Scraping {url} with date {target_date.strftime('%Y-%m-%d')}")
        
        # Pass the target_date parameter to scrape_comic
        metadata = scrape_comic('adamathome', url=url, target_date=target_date)
        if metadata:
            entries.append(metadata)
            logger.info(f"Successfully scraped comic from {url}")
            logger.info(f"Title: {metadata['title']}")
            logger.info(f"Image URL: {metadata['image']}")
        else:
            logger.error(f"Failed to scrape {url}")
    
    # Regenerate the feed
    if entries:
        if regenerate_feed(comic_info, entries):
            logger.info(f"Feed regenerated with {len(entries)} entries!")
            logger.info("Check feeds/adamathome.xml to see the results")
        else:
            logger.error("Failed to regenerate feed")
    else:
        logger.error("No entries to add to feed")

if __name__ == "__main__":
    main() 