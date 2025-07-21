#!/usr/bin/env python3
"""
Test script for Peanuts comic scraping with enhanced validation
"""

import logging
from datetime import datetime, timedelta
import pytz
import sys
# Ensure the script can find the update_feeds module
# This might require adjustments depending on your project structure
try:
    from scripts.update_feeds import scrape_comic, regenerate_feed
except ImportError:
    # If running directly from root, might need to adjust path
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from scripts.update_feeds import scrape_comic, regenerate_feed
    
import requests
from collections import defaultdict
import pprint # Use pprint for slightly cleaner dictionary printing

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Use a specific logger name for this test
logger = logging.getLogger("test_peanuts")

# Re-use the timezone from the main script
TIMEZONE = pytz.timezone('US/Eastern')

def validate_comic_url(url, date_str):
    """Validate that a comic URL exists and contains the expected date."""
    # This validation might be less reliable if GoComics redirects, but good first check
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Allow redirects to check the final URL status
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        
        final_url = response.url
        
        # Basic check: Status code is 200 (OK)
        status_ok = response.status_code == 200
        
        # Optional stricter check: does the final URL contain the date? 
        # This might fail if GoComics redirects to a non-dated landing page sometimes.
        # date_in_final_url = date_str in final_url 
        
        if not status_ok:
             logger.warning(f"URL validation failed for {url}. Status: {response.status_code}")
             if response.history:
                 logger.warning(f"  Redirected from: {url}")
                 logger.warning(f"  Final URL: {final_url}")
             return False
             
        # If we get here, status is OK. We can proceed with scraping.
        # The scrape function itself will handle content errors.
        return True
        
    except requests.RequestException as e:
        logger.error(f"Error checking URL {url}: {e}")
        return False
    except Exception as e:
        # Catch any other unexpected errors during validation
        logger.error(f"Unexpected error validating URL {url}: {e}")
        return False

def test_peanuts(days_to_test=5):
    """Tests scraping and feed generation for Peanuts."""
    # Test comic info specific to Peanuts
    comic_info = {
        "name": "Peanuts",
        "slug": "peanuts",
        "url": "https://www.gocomics.com/peanuts",
        "description": "Classic Peanuts comic strip by Charles Schulz" # Added description
    }
    
    logger.info(f"Starting Peanuts test - scraping last {days_to_test} days.")
    
    # Get dates in chronological order (oldest to newest)
    today = datetime.now(TIMEZONE)
    # Generate datetime objects first
    test_date_objects = [
        (today - timedelta(days=i))
        for i in range(days_to_test - 1, -1, -1) # e.g., for 5 days: 4 days ago -> today
    ]
    
    entries = []
    seen_images = defaultdict(list) # Track which dates use which images
    
    logger.info("Scraping Peanuts comics:")
    print("-" * 50) # Use print for visual separation in test output
    
    # Scrape comics in chronological order
    for date_obj in test_date_objects:
        # Format date for URL and logging
        formatted_date_url = date_obj.strftime('%Y/%m/%d')
        formatted_date_log = date_obj.strftime('%Y-%m-%d')
        
        print(f"\nTrying date: {formatted_date_log}") # Print for clarity
        print(f"Expected day: {date_obj.strftime('%A, %B %d')}")
        
        comic_url = f"https://www.gocomics.com/{comic_info['slug']}/{formatted_date_url}"
        
        # Optional: Validate URL first (can be skipped if causing issues)
        # print(f"Checking URL: {comic_url}")
        # if not validate_comic_url(comic_url, formatted_date_url):
        #     print(f"❌ URL validation skipped or failed for {formatted_date_log}")
            # continue # Skip if validation fails - might skip valid pages on redirect

        # Call the main scrape_comic function
        # Pass date string in YYYY/MM/DD format as expected by current scrape_comic
        metadata = scrape_comic(comic_info, formatted_date_url) 
        
        if metadata:
            # Check for duplicate images using the 'image' key from metadata
            image_url = metadata.get('image') # Use .get for safety
            if not image_url:
                 print("❌ Metadata found, but 'image' key is missing or empty.")
                 print(metadata)
                 continue # Skip if no image URL

            if seen_images[image_url]:
                print(f"⚠️  Warning: Image {image_url.split('/')[-1].split('?')[0]} already used for date(s): {', '.join(seen_images[image_url])}")
            seen_images[image_url].append(formatted_date_log)
            
            # Convert pub_date string (YYYY-MM-DD) back to datetime for consistency if needed later
            # Note: regenerate_feed likely handles sorting based on its own logic now
            try:
                 metadata['pub_date_obj'] = datetime.strptime(metadata['pub_date'], '%Y-%m-%d').replace(tzinfo=TIMEZONE)
            except (ValueError, KeyError):
                 print(f"❌ Error parsing pub_date string: {metadata.get('pub_date')}")
                 metadata['pub_date_obj'] = date_obj # Fallback to original date object

            entries.append(metadata)
            print(f"✅ Successfully scraped comic")
            print(f"  Title: {metadata.get('title', 'N/A')}")
            print(f"  Image URL: {image_url}")
            # Extract image ID from URL for easier comparison
            image_id = image_url.split('/')[-1].split('?')[0]
            print(f"  Image ID: {image_id}")
            print(f"  Pub Date Str: {metadata.get('pub_date', 'N/A')}")
            
        else:
            print(f"❌ Failed to scrape comic for {formatted_date_log} (scrape_comic returned None)")
    
    print("-" * 50)
    
    if entries:
        print(f"\nCollected {len(entries)} entries. Generating feed...")
        
        # Sort entries by date object (newest first for feed) before generating
        # Use the datetime object we added for reliable sorting
        entries.sort(key=lambda x: x.get('pub_date_obj', datetime.min.replace(tzinfo=TIMEZONE)), reverse=True)

        # Call regenerate_feed - use comic_info and the collected, sorted entries
        if regenerate_feed(comic_info, entries):
            print(f"✅ Successfully generated feed: public/feeds/{comic_info['slug']}.xml")
            
            # Optional: Print summary of image usage
            print("\nImage usage summary:")
            print("-" * 50)
            for image_url, dates in seen_images.items():
                image_id = image_url.split('/')[-1].split('?')[0]
                print(f"Image {image_id}:")
                for date_log in sorted(dates): # Print dates chronologically
                    print(f"  - {date_log}")
            
            # Optional: Print entries in generated feed order (newest first)
            print("\nEntries in generated feed order (newest first):")
            print("-" * 50)
            for entry in entries:
                 pub_date_str = entry.get('pub_date_obj', date_obj).strftime('%Y-%m-%d')
                 title = entry.get('title', 'N/A')
                 image_id = entry.get('image', '').split('/')[-1].split('?')[0]
                 print(f"Date: {pub_date_str} - {title}")
                 print(f"  Image ID: {image_id}")
                 print("---")
        else:
            print("❌ Failed to generate feed via regenerate_feed")
    else:
        print("\n❌ No entries found to generate feed")

if __name__ == '__main__':
    # Allows running like: python test_peanuts.py [number_of_days]
    num_days = 5
    if len(sys.argv) > 1:
        try:
            num_days = int(sys.argv[1])
        except ValueError:
            print("Usage: python test_peanuts.py [number_of_days_to_test]")
            sys.exit(1)
            
    test_peanuts(days_to_test=num_days) 