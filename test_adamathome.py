#!/usr/bin/env python3
"""
Test script for Adam@Home comic scraping with enhanced validation
"""

import logging
from datetime import datetime, timedelta
import pytz
from scripts.update_feeds import scrape_comic, regenerate_feed
import requests
from collections import defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_comic_url(url, date_str):
    """Validate that a comic URL exists and contains the expected date."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, allow_redirects=True)
        
        if response.history:
            print(f"⚠️  URL was redirected:")
            print(f"   Original: {url}")
            print(f"   Final: {response.url}")
            
        return response.status_code == 200 and response.url == url
    except Exception as e:
        print(f"Error checking URL {url}: {e}")
        return False

def test_adamathome():
    # Test comic info
    comic_info = {
        "name": "Adam@Home",
        "slug": "adamathome",
        "url": "https://www.gocomics.com/adamathome",
        "description": "Daily Adam@Home comic strip"
    }
    
    # Get last 5 days in chronological order (oldest to newest)
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern)
    test_dates = [
        (today - timedelta(days=i))
        for i in range(4, -1, -1)  # Start from 4 days ago to today
    ]
    
    entries = []
    seen_images = defaultdict(list)  # Track which dates use which images
    print("\nScraping Adam@Home comics:")
    print("-" * 50)
    
    # Scrape comics in chronological order
    for date in test_dates:
        formatted_date = date.strftime('%Y/%m/%d')
        print(f"\nTrying date: {formatted_date}")
        print(f"Expected day: {date.strftime('%A, %B %d')}")
        
        # First validate the comic URL
        comic_url = f"https://www.gocomics.com/adamathome/{formatted_date}"
        print(f"Checking URL: {comic_url}")
        if not validate_comic_url(comic_url, formatted_date):
            print(f"❌ URL validation failed for {formatted_date}")
            continue
        
        metadata = scrape_comic(comic_info, formatted_date)
        if metadata:
            # Check for duplicate images
            image_url = metadata['image_url']
            if seen_images[image_url]:
                print(f"⚠️  Warning: Image already used for date(s): {', '.join(seen_images[image_url])}")
            seen_images[image_url].append(formatted_date)
            
            entries.append(metadata)
            print(f"✅ Successfully scraped comic")
            print(f"Title: {metadata['title']}")
            print(f"Image URL: {metadata['image_url']}")
            print(f"Publication Date: {metadata['pub_date']}")
            
            # Extract image ID from URL for easier comparison
            image_id = image_url.split('/')[-1].split('?')[0]
            print(f"Image ID: {image_id}")
        else:
            print(f"❌ Failed to scrape comic for {formatted_date}")
    
    if entries:
        print("\nGenerating feed...")
        if regenerate_feed(comic_info, entries):
            print("✅ Successfully generated feed")
            print(f"Total entries: {len(entries)}")
            
            # Print summary of image usage
            print("\nImage usage summary:")
            print("-" * 50)
            for image_url, dates in seen_images.items():
                image_id = image_url.split('/')[-1].split('?')[0]
                print(f"Image {image_id}:")
                for date in dates:
                    print(f"  - {date}")
            
            # Print entries in chronological order
            print("\nEntries in chronological order:")
            print("-" * 50)
            for entry in entries:
                print(f"Date: {entry['pub_date'].strftime('%Y-%m-%d')} - {entry['title']}")
                image_id = entry['image_url'].split('/')[-1].split('?')[0]
                print(f"Image ID: {image_id}")
                print("-" * 30)
        else:
            print("❌ Failed to generate feed")
    else:
        print("\n❌ No entries found to generate feed")

if __name__ == '__main__':
    test_adamathome() 