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
            
            # Look for the main comic container first
            comic_container = soup.find('div', class_='ComicViewer_comicViewer__comic__oftX6')
            if not comic_container:
                logging.warning(f"Could not find comic container for {comic['name']} on {date_str}")
                return None
                
            # Find all images in the container
            comic_images = []
            for img in comic_container.find_all('img'):
                classes = img.get('class', [])
                src = img.get('src', '')
                
                # Skip social media preview images and staging assets
                if 'GC_Social_FB' in src or 'staging-assets' in src:
                    continue
                    
                # Check for both required classes
                if ('Comic_comic__image__6e_Fw' in classes and 
                    'Comic_comic__image_strip__hPLFq' in classes):
                    comic_images.append(img)
            
            # If we found multiple valid images, use the first one
            if comic_images:
                comic_image = comic_images[0]
                # Extract image URL and clean it
                image_url = comic_image.get('src', '').split('?')[0]  # Remove any query parameters
                alt_text = comic_image.get('alt', '')
                
                return {
                    'image_url': image_url,
                    'alt_text': alt_text
                }
            else:
                logging.warning(f"No valid comic strip image found for {comic['name']} on {date_str}")
                return None
            
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
    
    # Check if entry already exists
    if any(entry['id'] == entry_id for entry in existing_entries):
        logging.info(f"Entry for {comic['name']} on {date_str} already exists")
        return None
        
    comic_data = scrape_comic(comic, date_str)
    if not comic_data:
        return None
        
    # Create description with alt text if available
    description = f"{comic['name']} for {date_str}"
    if comic_data.get('alt_text'):
        description = f"{description}\n\n{comic_data['alt_text']}"
        
    return {
        'id': entry_id,
        'title': f"{comic['name']} - {date_str}",
        'url': f"https://www.gocomics.com/{comic['slug']}/{date_str}",
        'image_url': comic_data['image_url'],
        'description': description,
        'pub_date': date
    }

def load_existing_entries(feed_path):
    """Load existing entries from a feed file."""
    entries = []
    seen_dates = set()  # Track unique dates to prevent duplicates
    try:
        if os.path.exists(feed_path):
            feed = feedparser.parse(feed_path)
            for entry in feed.entries:
                # Extract date from title
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', entry.title)
                if not date_match:
                    continue
                entry_date = date_match.group(0)
                
                # Skip if we already have an entry for this date
                if entry_date in seen_dates:
                    continue
                
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
                    seen_dates.add(entry_date)
                    entries.append({
                        'title': entry.title,
                        'url': entry.link,
                        'image_url': image_url,
                        'description': entry.description,
                        'pub_date': entry.get('published', ''),
                        'id': entry.get('id', '')
                    })
    except Exception as e:
        logging.error(f"Error loading existing entries from {feed_path}: {e}")
    
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
    
    # Get last 5 days of comics in chronological order (oldest to newest)
    today = datetime.now(TIMEZONE)
    test_dates = [
        (today - timedelta(days=i))
        for i in range(4, -1, -1)  # Start from 4 days ago to today
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
        
        # Sort all entries by date in reverse chronological order (newest first)
        all_entries.sort(
            key=lambda x: datetime.strptime(x['pub_date'], '%a, %d %b %Y %H:%M:%S %z').timestamp() 
            if isinstance(x['pub_date'], str) 
            else x['pub_date'].timestamp(),
            reverse=True
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