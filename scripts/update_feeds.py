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

def scrape_comic(comic_info, date_str):
    """Scrape a comic for a specific date."""
    # Convert slashes to dashes for datetime parsing
    date_for_parsing = date_str.replace('/', '-')
    comic_date = datetime.strptime(date_for_parsing, "%Y-%m-%d")
    title = f"{comic_info['name']} - {date_for_parsing}"
    url = f"{COMICS_URL}/{comic_info['slug']}/{date_str}"
    
    try:
        response = requests.get(url, headers=get_headers())
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {comic_info['name']} for {date_str}: HTTP {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the comic image - look for the specific class and domain
        comic_img = None
        
        # Look for images with the specific comic class
        comic_images = soup.find_all('img', class_='Comic_comic__image__6e_Fw')
        for img in comic_images:
            src = img.get('src', '')
            if src and 'featureassets.gocomics.com' in src:
                # Prefer images that also have the strip class
                if 'Comic_comic__image_strip__hPLFq' in img.get('class', []):
                    comic_img = src
                    break
                # If we haven't found an image yet, use this one
                elif not comic_img:
                    comic_img = src
        
        if not comic_img:
            logger.error(f"Could not find any valid comic image for {comic_info['name']} on {date_str}")
            return None
            
        logger.info(f"Found comic image for {comic_info['name']} on {date_str}: {comic_img}")
        
        # Get the alt text which often contains the comic dialogue
        alt_text = next((img.get('alt', '') for img in comic_images if img.get('src') == comic_img), '')
        
        # Create description with the alt text if available
        description = f"{comic_info['name']} for {date_str}"
        if alt_text:
            description = f"{description}\n\n{alt_text}"
        
        return {
            'id': f"{comic_info['slug']}_{date_str}",
            'title': title,
            'url': url,
            'image_url': comic_img,
            'description': description,
            'pub_date': comic_date
        }
            
    except Exception as e:
        logger.error(f"Error scraping {comic_info['name']} for {date_str}: {e}")
        return None

def load_existing_entries(feed_path):
    """Load existing entries from a feed file."""
    entries = []
    try:
        if os.path.exists(feed_path):
            feed = feedparser.parse(feed_path)
            for entry in feed.entries:
                # Look for image URL in enclosures first
                image_url = ""
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if enclosure.get('type', '').startswith('image/'):
                            image_url = enclosure.get('href', '')
                            break
                
                # Extract image from description if no enclosure found
                if not image_url and hasattr(entry, 'description'):
                    # Basic extraction of image URL from description
                    match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
                    if match:
                        image_url = match.group(1)
                
                # Create entry dictionary
                entries.append({
                    'title': entry.title,
                    'url': entry.link,
                    'image_url': image_url,  # Properly named field with extracted image URL
                    'pub_date': entry.published,
                    'description': entry.description,
                    'id': entry.id
                })
    except Exception as e:
        logger.error(f"Error loading existing entries from {feed_path}: {e}")
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

def update_feed(comic_info, metadata):
    """Update a comic's feed with a new entry."""
    try:
        # Create feed generator
        fg = ComicFeedGenerator()
        
        # Load existing entries
        feed_path = os.path.join('public', 'feeds', f"{comic_info['slug']}.xml")
        existing_entries = load_existing_entries(feed_path)
        
        # Add new entry if it doesn't exist
        if metadata and not any(e['id'] == metadata['id'] for e in existing_entries):
            existing_entries.append(metadata)
            logger.info(f"Added new entry to feed for {comic_info['name']}")
        else:
            logger.info(f"No new entries to add for {comic_info['name']}")
            return True  # Return success even if no new entries
        
        # Generate feed with all entries
        if fg.generate_feed(comic_info, existing_entries):
            logger.info(f"Updated feed for {comic_info['name']} with {len(existing_entries)} entries")
            return True
        else:
            logger.error(f"Failed to update feed for {comic_info['name']}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating feed for {comic_info['name']}: {e}")
        return False

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

def update_all_feeds():
    """Update all comic feeds."""
    comics = load_comics_list()
    success_count = 0
    total_count = len(comics)
    updated_count = 0
    
    # Get last 5 days of comics
    today = datetime.now(TIMEZONE)
    test_dates = [
        (today - timedelta(days=i))
        for i in range(5)  # Get last 5 days
    ]
    
    for comic in comics:  # Process all comics
        entries = []
        has_new_content = False
        
        # Scrape last 5 days
        for date in test_dates:
            formatted_date = date.strftime('%Y/%m/%d')
            metadata = scrape_comic(comic, formatted_date)
            if metadata:
                entries.append(metadata)
                logger.info(f"Successfully scraped {comic['name']} for {formatted_date}")
                has_new_content = True
        
        if entries:
            # Check if we need to regenerate the feed
            if should_regenerate_feed(comic):
                # Regenerate the entire feed
                if regenerate_feed(comic, entries):
                    success_count += 1
                    updated_count += 1
                    logger.info(f"Successfully regenerated feed for {comic['name']} with {len(entries)} entries")
            else:
                # Just update with new entries
                if update_feed(comic, entries[0] if entries else None):
                    success_count += 1
                    if has_new_content:
                        updated_count += 1
                        logger.info(f"Successfully updated feed for {comic['name']} with new content")
                    else:
                        logger.info(f"No new content for {comic['name']}, feed not updated")
    
    # Clean up old tokens
    cleanup_old_tokens()
    
    logger.info(f"Updated {updated_count} out of {total_count} feeds with new content")
    logger.info(f"Successfully processed {success_count} out of {total_count} feeds")
    return success_count, total_count

if __name__ == '__main__':
    update_all_feeds() 