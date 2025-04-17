#!/usr/bin/env python3

import logging
from scripts.update_feeds import scrape_comic
from datetime import datetime, timedelta
import pytz

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_comic_date(comic_info, date_str):
    print(f"\nTesting comic for date: {date_str}")
    print("-" * 50)
    
    # Try to scrape the comic
    result = scrape_comic(comic_info, date_str)
    
    if result:
        print("\nScraping Results:")
        print(f"Title: {result['title']}")
        print(f"Image URL: {result['image_url']}")
        print(f"Description: {result['description']}")
        print(f"URL: {result['url']}")
        
        # Verify image URL contains expected domain
        if 'featureassets.gocomics.com' in result['image_url']:
            print("\n✅ Image URL is from correct domain")
        else:
            print("\n❌ Image URL is from unexpected domain")
            
    else:
        print("\n❌ Failed to scrape comic")
    
    return result is not None

def test_comic_scraper():
    # Test comic info
    comic_info = {
        "name": "Adam@Home",
        "slug": "adamathome",
        "description": "Test comic for image selection"
    }
    
    # Get today's date in US/Eastern timezone
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern)
    yesterday = today - timedelta(days=1)
    
    # Test both dates
    dates_to_test = [
        today.strftime('%Y/%m/%d'),
        yesterday.strftime('%Y/%m/%d')
    ]
    
    success = True
    for date_str in dates_to_test:
        if not test_comic_date(comic_info, date_str):
            success = False
    
    if success:
        print("\n✅ All tests passed successfully!")
    else:
        print("\n❌ Some tests failed!")

if __name__ == '__main__':
    test_comic_scraper() 