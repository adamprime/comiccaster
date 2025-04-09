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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple selectors for the image
        img_elem = None
        selectors = [
            'img[class*="strip"]',  # Original selector
            'picture.item-comic-image img',  # New potential selector
            '.comic__image img',    # Another potential selector
            '.container img[alt*="comic"]',  # Generic selector
            '.js-comic img'         # Another possible selector
        ]
        
        for selector in selectors:
            img_elem = soup.select_one(selector)
            if img_elem and img_elem.get('src'):
                break
                
        if not img_elem or not img_elem.get('src'):
            # Try OpenGraph image as fallback
            og_image = soup.select_one('meta[property="og:image"]')
            if og_image and og_image.get('content'):
                image_url = og_image.get('content')
            else:
                logger.warning(f"No image found for {slug}")
                return None
        else:
            image_url = img_elem.get('src', '')
        
        # Extract title - try multiple approaches
        title = None
        
        # Method 1: Standard h1 title
        title_elem = soup.select_one('h1.item-comic-title')
        if title_elem:
            title = title_elem.text.strip()
        
        # Method 2: Regular h1
        if not title:
            title_elem = soup.select_one('h1')
            if title_elem:
                title = title_elem.text.strip()
        
        # Method 3: OpenGraph title
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title:
                title = og_title.get('content', '')
        
        # Fallback title
        if not title:
            title = f"{slug.replace('-', ' ').title()} - {datetime.now().strftime('%Y-%m-%d')}"
        
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
        
        # Extract description
        description = f"Latest {slug.replace('-', ' ').title()} comic strip"
        og_desc = soup.select_one('meta[property="og:description"]')
        if og_desc and og_desc.get('content'):
            description = og_desc.get('content')
        
        return {
            'title': title,
            'url': url,
            'image': image_url,
            'pub_date': pub_date_str,
            'description': description,
            'id': url  # Ensure id field exists to prevent errors
        }
    except Exception as e:
        logger.error(f"Error scraping {slug}: {e}")
        return None

def update_feed(comic_info, metadata):
    """Update a comic's feed with a new entry."""
    try:
        # Create feed generator
        fg = ComicFeedGenerator()
        
        # Update the feed
        if fg.update_feed(comic_info, metadata):
            logger.info(f"Updated feed for {comic_info['name']}")
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
    
    # Exit with error only if less than 30% of feeds were updated
    # This is a more reasonable threshold since many comics don't update daily
    # and some may be discontinued or on hiatus
    if success_count < total_count * 0.3:
        logger.error(f"Only {(success_count/total_count)*100:.1f}% of feeds were updated successfully. This is unusually low and might indicate a problem.")
        sys.exit(1)

if __name__ == '__main__':
    update_all_feeds() 