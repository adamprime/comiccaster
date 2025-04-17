#!/usr/bin/env python3

from scripts.update_feeds import scrape_comic
from comiccaster.feed_generator import ComicFeedGenerator
from datetime import datetime, timedelta
import pytz
import os

# Set timezone to US/Eastern (GoComics timezone)
TIMEZONE = pytz.timezone('US/Eastern')

def test_calvin_feed():
    # Comic info
    comic_info = {
        'name': 'Calvin and Hobbes',
        'slug': 'calvinandhobbes',
        'description': 'Calvin and Hobbes by Bill Watterson',
        'author': 'Bill Watterson',
        'url': 'https://www.gocomics.com/calvinandhobbes',
        'feed_url': 'https://www.gocomics.com/calvinandhobbes/rss'
    }
    
    # Get last 5 days of comics in chronological order (oldest to newest)
    today = datetime.now(TIMEZONE)
    test_dates = [
        (today - timedelta(days=i))
        for i in range(4, -1, -1)  # Start from 4 days ago to today
    ]
    
    entries = []
    
    # Scrape last 5 days in chronological order
    for date in test_dates:
        formatted_date = date.strftime('%Y/%m/%d')
        print(f"Scraping comic for {formatted_date}...")
        metadata = scrape_comic(comic_info, formatted_date)
        if metadata:
            entries.append(metadata)
            print(f"Successfully scraped comic for {formatted_date}")
    
    if entries:
        # Create test feeds directory if it doesn't exist
        os.makedirs('test_feeds', exist_ok=True)
        
        # Generate feed
        fg = ComicFeedGenerator()
        feed_path = os.path.join('test_feeds', f"{comic_info['slug']}.xml")
        if fg.generate_feed(comic_info, entries):
            print(f"\nSuccessfully generated feed with {len(entries)} entries")
            print(f"Feed saved to: {feed_path}")
        else:
            print("Failed to generate feed")
    else:
        print("No entries found to create feed")

if __name__ == '__main__':
    test_calvin_feed() 