#!/usr/bin/env python3
"""
Update script for ComicCaster feeds
Runs daily to update all comic feeds with the latest content
"""

import json
import os
import logging
import sys
from datetime import datetime, timedelta, timezone
import pytz
import requests
from bs4 import BeautifulSoup
from comiccaster.feed_generator import ComicFeedGenerator
from feedgen.entry import FeedEntry
import feedparser
import configparser
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml
from dateutil import parser as date_parser
import concurrent.futures
from functools import partial

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set timezone to US/Eastern (GoComics timezone)
TIMEZONE = pytz.timezone('US/Eastern')

# GoComics base URL
COMICS_URL = "https://www.gocomics.com"

# Constants for concurrent processing
MAX_WORKERS = 10  # Maximum number of concurrent workers
REQUEST_TIMEOUT = 10  # Timeout for HTTP requests in seconds
MAX_RETRIES = 3  # Maximum number of retries for failed requests

def load_comics_list():
    """Load the list of comics from comics_list.json."""
    try:
        with open('comics_list.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
        sys.exit(1)

def get_headers():
    """Get browser-like headers for HTTP requests."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

def scrape_comic(comic, date_str, timeout=REQUEST_TIMEOUT, retries=MAX_RETRIES):
    """Scrape a comic from GoComics for a given date."""
    logging.info(f"Fetching {comic['name']} for {date_str}")
    
    for attempt in range(retries):
        try:
            # Format the date correctly for the URL
            if '/' in date_str:
                # If date is already in URL format (YYYY/MM/DD), use as is
                url = f"https://www.gocomics.com/{comic['slug']}/{date_str}"
            else:
                # Convert YYYY-MM-DD to URL format
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                url = f"https://www.gocomics.com/{comic['slug']}/{target_date.strftime('%Y/%m/%d')}"
        
            response = requests.get(url, headers=get_headers(), timeout=timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract the comic image URL (prioritizing the actual comic)
            comic_image = None
            
            # Try to find the comic image URL in the JSON data embedded in script tags
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    if script.string and "ImageObject" in script.string and "contentUrl" in script.string:
                        data = json.loads(script.string)
                        if data.get("@type") == "ImageObject" and data.get("contentUrl") and "featureassets.gocomics.com" in data.get("contentUrl"):
                            comic_image = data.get("contentUrl")
                            logging.info(f"Found actual comic image in JSON data for {url}")
                            break
                except Exception as e:
                    logging.warning(f"Error parsing JSON data in script tag: {e}")
            
            # Try to extract from JSON data within Next.js script payloads
            if not comic_image:
                for script in soup.find_all("script"):
                    if script.string and "featureassets.gocomics.com/assets" in script.string and "url" in script.string:
                        try:
                            # Find URLs that look like comic strip images
                            matches = re.findall(r'"url"\s*:\s*"(https://featureassets\.gocomics\.com/assets/[^"]+)"', script.string)
                            if matches:
                                comic_image = matches[0]
                                logging.info(f"Found comic image URL in script data for {url}")
                                break
                        except Exception as e:
                            logging.warning(f"Error extracting URL from script: {e}")
            
            # If no comic image found in scripts, try the social media image as fallback
            if not comic_image:
                meta_tag = soup.select_one('meta[property="og:image"]')
                if meta_tag and meta_tag.get("content"):
                    comic_image = meta_tag["content"]
                    logging.info(f"Found social media image for {url}")
            
            if not comic_image:
                logging.error(f"No comic image found for {url}")
                return None
            
            # Get the comic URL (which might be different than the constructed URL)
            comic_url = url
            
            # Parse publication date from URL
            pub_date_str = date_str.replace("/", "-")
            
            # Create title from date
            title = f"{comic['name']} - {target_date.strftime('%Y-%m-%d')}"
            
            # Don't include the image in the description, as it will be handled separately
            description_text = f'Comic strip for {target_date.strftime("%Y-%m-%d")}'
            
            # Parse the date and convert to datetime and UTC
            pub_date = target_date.replace(tzinfo=pytz.UTC)
            
            # Use the image URL for the image field, but don't duplicate it in the description
            # This will prevent the image from appearing twice in the feed
            return {
                'title': title,
                'url': url,
                'image': comic_image,
                'pub_date': pub_date_str,
                'description': description_text,
                'id': url  # Use URL as ID to ensure uniqueness
            }
            
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(1)  # Wait before retrying
                continue
            logging.warning(f"Failed to fetch {comic['name']} for {date_str} after {retries} attempts: {str(e)}")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error fetching {comic['name']} for {date_str}: {str(e)}")
            return None

def process_comic_date(comic, date, existing_entries):
    """Process a single comic for a specific date."""
    date_str = date.strftime('%Y-%m-%d')
    entry_id = f"{comic['slug']}_{date_str}"
    
    # Check if entry already exists with the same date
    existing_entry = next(
        (entry for entry in existing_entries if entry['id'] == entry_id),
        None
    )
    
    if existing_entry:
        logging.info(f"Entry for {comic['name']} on {date_str} already exists")
        return None
        
    comic_data = scrape_comic(comic, date_str)
    if not comic_data:
        return None
        
    # Add the entry ID to the comic data
    comic_data['id'] = entry_id
    
    # The scrape_comic function now returns the complete entry data
    return comic_data

def load_existing_entries(feed_path):
    """Load existing entries from a feed file."""
    entries = []
    seen_dates = {}  # Track entries by date and use latest version
    try:
        if os.path.exists(feed_path):
            feed = feedparser.parse(feed_path)
            for entry in feed.entries:
                # Extract date from title
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', entry.title)
                if not date_match:
                    continue
                entry_date = date_match.group(0)
                
                # Parse the publication date
                pub_date = None
                if hasattr(entry, 'published'):
                    try:
                        pub_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')
                    except (ValueError, TypeError):
                        # If parsing fails, use current time
                        pub_date = datetime.now(timezone.utc)
                
                # Look for image URL in enclosures first
                image_url = ""
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if enclosure.get('type', '').startswith('image/'):
                            url = enclosure.get('href', '')
                            # Skip social media preview images and staging assets
                            if 'GC_Social_FB' not in url and 'staging-assets' not in url:
                                image_url = url
                                break
                
                # Extract image from description if no enclosure found
                if not image_url and hasattr(entry, 'description'):
                    # Look for img tag in description
                    match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
                    if match:
                        url = match.group(1)
                        # Skip social media preview images and staging assets
                        if 'GC_Social_FB' not in url and 'staging-assets' not in url:
                            image_url = url
                
                # Only add entry if we found a valid image URL
                if image_url:
                    entry_data = {
                        'title': entry.title,
                        'url': entry.link,
                        'image_url': image_url,
                        'description': entry.description,
                        'pub_date': pub_date.strftime('%a, %d %b %Y %H:%M:%S %z') if pub_date else '',
                        'id': entry.get('id', f"{entry.link}#{entry_date}")
                    }
                    
                    # Keep only the latest version of an entry for a given date
                    if entry_date not in seen_dates or pub_date > seen_dates[entry_date]['pub_date']:
                        seen_dates[entry_date] = {
                            'entry': entry_data,
                            'pub_date': pub_date
                        }
    except Exception as e:
        logging.error(f"Error loading existing entries from {feed_path}: {e}")
    
    # Add only the latest version of each entry
    entries = [data['entry'] for data in seen_dates.values()]
    return entries

def regenerate_feed(comic_info, entries):
    """Regenerate a comic's feed with all entries sorted by date."""
    try:
        # Get path to the feed file
        feed_path = os.path.join('public', 'feeds', f"{comic_info['slug']}.xml")
        
        # Create feed generator and generate sorted feed
        fg = ComicFeedGenerator()
        if fg.generate_feed(comic_info, entries):
            logger.info(f"Regenerated feed for {comic_info['name']} with {len(entries)} entries")
            return True
        return False
    except Exception as e:
        logger.error(f"Error regenerating feed for {comic_info['name']}: {e}")
        return False

def update_feed(comic, feed_dir='feeds'):
    """Update a comic's feed with new entries."""
    # Ensure feed directory exists
    os.makedirs(feed_dir, exist_ok=True)
    
    # Get feed path
    feed_path = os.path.join(feed_dir, f"{comic['slug']}.xml")
    
    # Load existing entries
    existing_entries = load_existing_entries(feed_path)
    
    # Get last 10 days of comics in chronological order (oldest to newest)
    today = datetime.now(TIMEZONE)
    test_dates = [
        (today - timedelta(days=i))
        for i in range(9, -1, -1)  # Start from 9 days ago to today
    ]
    
    # Process dates concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Create a partial function with the comic and existing_entries arguments
        process_func = partial(process_comic_date, comic, existing_entries=existing_entries)
        # Map the function over the dates
        future_to_date = {executor.submit(process_func, date): date for date in test_dates}
        
        new_entries = []
        for future in concurrent.futures.as_completed(future_to_date):
            date = future_to_date[future]
            try:
                entry = future.result()
                if entry:
                    new_entries.append(entry)
                    logging.info(f"Added new entry for {comic['name']} on {date.strftime('%Y-%m-%d')}")
            except Exception as e:
                logging.error(f"Error processing {comic['name']} for {date}: {e}")

    if new_entries:
        # Add new entries to existing ones
        all_entries = existing_entries + new_entries
        
        # Sort all entries by date in chronological order (oldest first)
        all_entries.sort(
            key=lambda x: datetime.strptime(x['pub_date'], '%a, %d %b %Y %H:%M:%S %z').timestamp() 
            if isinstance(x['pub_date'], str) 
            else x['pub_date'].timestamp()
        )
        
        # Initialize feed generator and generate feed
        feed_generator = ComicFeedGenerator()
        if feed_generator.generate_feed(comic, all_entries):
            logging.info(f"Updated feed for {comic['name']} with {len(new_entries)} new entries")
            return True
        else:
            logging.error(f"Failed to generate feed for {comic['name']}")
            return False
    
    return True

def cleanup_old_tokens():
    """Remove tokens older than 7 days."""
    try:
        token_dir = 'tokens'
        if not os.path.exists(token_dir):
            return
        
        for filename in os.listdir(token_dir):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(token_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            
            if datetime.now() - file_time > timedelta(days=7):
                os.remove(filepath)
                logger.info(f"Removed old token: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning up old tokens: {e}")

def should_regenerate_feed(comic_info):
    """Check if a feed should be regenerated based on time or entry count."""
    feed_path = os.path.join('public', 'feeds', f"{comic_info['slug']}.xml")
    
    # Always regenerate if feed doesn't exist
    if not os.path.exists(feed_path):
        return True
    
    try:
        # Check file modification time
        mtime = datetime.fromtimestamp(os.path.getmtime(feed_path))
        # Regenerate weekly
        if datetime.now() - mtime > timedelta(days=7):
            return True
        
        # Check number of entries
        feed = feedparser.parse(feed_path)
        # Regenerate if more than 100 entries (to maintain performance)
        if len(feed.entries) > 100:
            return True
            
    except Exception as e:
        logger.error(f"Error checking feed status for {comic_info['name']}: {e}")
        # If we can't check, default to not regenerating
        return False
    
    return False

def process_comic(comic):
    """Process a single comic."""
    try:
        logger.info(f"Processing {comic['name']}")
        update_feed(comic)
        logger.info(f"Successfully updated feed for {comic['name']} with new content")
        return True
    except Exception as e:
        logger.error(f"Error processing {comic['name']}: {e}")
        return False

def main():
    """Main function to update all comic feeds."""
    try:
        # Load comics list
        comics = load_comics_list()
        logger.info(f"Loaded {len(comics)} comics")
        
        # Process comics concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all comics for processing
            future_to_comic = {executor.submit(process_comic, comic): comic for comic in comics}
            
            # Process results as they complete
            successful = 0
            failed = 0
            for future in concurrent.futures.as_completed(future_to_comic):
                comic = future_to_comic[future]
                try:
                    if future.result():
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Error processing {comic['name']}: {e}")
                    failed += 1
            
            logger.info(f"Completed processing {len(comics)} comics: {successful} successful, {failed} failed")
        
        return 0
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 