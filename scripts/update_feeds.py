#!/usr/bin/env python3
"""
Update script for ComicCaster feeds
Runs daily to update all comic feeds with the latest content
"""

import json
import os
import logging
import sys
from datetime import datetime, timedelta
import pytz
import requests
from bs4 import BeautifulSoup
from comiccaster.feed_generator import ComicFeedGenerator
from feedgen.entry import FeedEntry
import feedparser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set timezone to US/Eastern (GoComics timezone)
TIMEZONE = pytz.timezone('US/Eastern')

def load_comics_list():
    """Load the list of comics from comics_list.json."""
    try:
        with open('comics_list.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
        sys.exit(1)

def scrape_comic(slug, url=None, target_date=None):
    """Scrape a comic from GoComics."""
    if url is None:
        url = f"https://www.gocomics.com/{slug}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get the OpenGraph image
        og_image = soup.select_one('meta[property="og:image"]')
        if not og_image or not og_image.get('content'):
            logger.warning(f"No OpenGraph image found for {url}")
            return None
            
        image_url = og_image.get('content')
        
        # Accept generic social media images - don't skip them
        # This is important for weekly/biweekly comics that may not have new content daily
        if 'GC_Social_FB_Generic' in image_url:
            logger.info(f"Generic social media image found for {url}, but continuing anyway")
        
        # Use target_date if provided
        if target_date:
            pub_date = target_date
        else:
            # Extract publication date and add timezone
            pub_date = None
            
            # Method 1: time element
            date_elem = soup.select_one('time')
            if date_elem and date_elem.get('datetime'):
                try:
                    pub_date = datetime.fromisoformat(date_elem.get('datetime').replace('Z', '+00:00'))
                except ValueError:
                    pass
            
            # Method 2: Article published date meta
            if not pub_date:
                published_meta = soup.select_one('meta[property="article:published_time"]')
                if published_meta and published_meta.get('content'):
                    try:
                        pub_date = datetime.fromisoformat(published_meta.get('content').replace('Z', '+00:00'))
                    except ValueError:
                        pass
            
            # Fallback: use current date
            if not pub_date:
                pub_date = datetime.now()
        
        # Ensure timezone is set
        if pub_date.tzinfo is None:
            pub_date = TIMEZONE.localize(pub_date)
        
        # Format pub_date as RFC 2822 string
        pub_date_str = pub_date.strftime('%a, %d %b %Y %H:%M:%S %z')
        
        # Create title from date
        title = f"{slug.replace('-', ' ').title()} - {pub_date.strftime('%Y-%m-%d')}"
        
        # Create description with image
        description = f'<img src="{image_url}" alt="{title}" />'
        
        return {
            'title': title,
            'url': url,
            'image': image_url,
            'pub_date': pub_date_str,
            'description': description,
            'id': url  # Use URL as ID to ensure uniqueness
        }
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return None

def load_existing_entries(feed_path):
    """Load existing entries from a feed file."""
    entries = []
    try:
        if os.path.exists(feed_path):
            feed = feedparser.parse(feed_path)
            for entry in feed.entries:
                entries.append({
                    'title': entry.title,
                    'url': entry.link,
                    'image': entry.description,  # Image URL is stored in description
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
            url = f"https://www.gocomics.com/{comic['slug']}/{formatted_date}"
            metadata = scrape_comic(comic['slug'], url=url, target_date=date)
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
    
    # Log summary
    logger.info(f"Updated {updated_count} out of {total_count} feeds with new content")
    logger.info(f"Successfully processed {success_count} out of {total_count} feeds")

if __name__ == '__main__':
    update_all_feeds() 