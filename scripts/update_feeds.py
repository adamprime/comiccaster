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
from feedgen.feed import FeedGenerator
from feedgen.entry import FeedEntry

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

def scrape_comic(slug):
    """Scrape the latest comic from GoComics."""
    url = f"https://www.gocomics.com/{slug}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract comic image
        img_elem = soup.select_one('img[class*="strip"]')
        if not img_elem:
            logger.warning(f"No image found for {slug}")
            return None
        
        image_url = img_elem.get('src', '')
        
        # Extract title
        title_elem = soup.select_one('h1')
        title = title_elem.text.strip() if title_elem else f"{slug} - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Extract publication date and add timezone
        date_elem = soup.select_one('time')
        if date_elem and date_elem.get('datetime'):
            pub_date = datetime.fromisoformat(date_elem.get('datetime').replace('Z', '+00:00'))
            pub_date = TIMEZONE.localize(pub_date)
        else:
            pub_date = TIMEZONE.localize(datetime.now())
        
        return {
            'title': title,
            'url': url,
            'image': image_url,
            'pub_date': pub_date,
            'description': f"Latest {slug} comic strip"
        }
    except Exception as e:
        logger.error(f"Error scraping {slug}: {e}")
        return None

def update_feed(comic_info, metadata):
    """Update a comic's feed with a new entry."""
    try:
        feed_path = f"feeds/{comic_info['slug']}.xml"
        
        # Create feed generator
        fg = FeedGenerator()
        fg.title(f"{comic_info['name']} - GoComics")
        fg.link(href=comic_info['url'])
        fg.description(f"Daily {comic_info['name']} comic strip by {comic_info.get('author', 'Unknown')}")
        fg.language('en')
        
        # Load existing feed if it exists
        if os.path.exists(feed_path):
            try:
                with open(feed_path, 'r') as f:
                    fg.rss_file(feed_path)
            except Exception as e:
                logger.warning(f"Could not load existing feed for {comic_info['name']}: {e}")
        
        # Create and add new entry
        fe = FeedEntry()
        fe.title(metadata['title'])
        fe.link(href=metadata['url'])
        
        # Create HTML description with the comic image
        description = f"""
        <div style="text-align: center;">
            <img src="{metadata['image']}" alt="{comic_info['name']}" style="max-width: 100%;">
            <p>{metadata.get('description', '')}</p>
        </div>
        """
        fe.description(description)
        
        # Set publication date
        fe.published(metadata['pub_date'])
        
        # Add entry to feed
        fg.add_entry(fe)
        
        # Save the feed
        os.makedirs(os.path.dirname(feed_path), exist_ok=True)
        fg.rss_file(feed_path)
        
        logger.info(f"Updated feed for {comic_info['name']}")
        return True
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

def update_all_feeds():
    """Update all comic feeds."""
    comics = load_comics_list()
    success_count = 0
    total_count = len(comics)
    
    for comic in comics:
        metadata = scrape_comic(comic['slug'])
        if metadata:
            if update_feed(comic, metadata):
                success_count += 1
    
    # Clean up old tokens
    cleanup_old_tokens()
    
    # Log summary
    logger.info(f"Updated {success_count} out of {total_count} feeds")
    
    # Exit with error if less than 90% of feeds were updated
    if success_count < total_count * 0.9:
        logger.error("Less than 90% of feeds were updated successfully")
        sys.exit(1)

if __name__ == '__main__':
    update_all_feeds() 