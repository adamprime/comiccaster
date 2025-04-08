#!/usr/bin/env python3
"""
Update script for ComicCaster feeds
Runs daily to update all comic feeds with the latest content
"""

import json
import os
import logging
from datetime import datetime
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

def load_comics_list():
    """Load the list of comics from comics_list.json."""
    with open('comics_list.json', 'r') as f:
        return json.load(f)

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
            return None
        
        image_url = img_elem.get('src', '')
        
        # Extract title
        title_elem = soup.select_one('h1')
        title = title_elem.text.strip() if title_elem else f"{slug} - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Extract publication date
        date_elem = soup.select_one('time')
        pub_date = date_elem.get('datetime') if date_elem else datetime.now().isoformat()
        
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
            fg.load(feed_path)
        
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
        fg.rss_file(feed_path)
        logger.info(f"Updated feed for {comic_info['name']} at {feed_path}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to update feed for {comic_info['name']}: {e}")
        return False

def update_all_feeds():
    """Update all comic feeds with the latest content."""
    # Load comics list
    comics = load_comics_list()
    logger.info(f"Loaded {len(comics)} comics from comics_list.json")
    
    # Update each comic's feed
    success_count = 0
    for comic in comics:
        # Scrape the latest comic
        metadata = scrape_comic(comic['slug'])
        if not metadata:
            logger.warning(f"Failed to scrape comic: {comic['name']}")
            continue
        
        # Update the feed
        success = update_feed(comic, metadata)
        if success:
            logger.info(f"Updated feed for {comic['name']}")
            success_count += 1
        else:
            logger.warning(f"Failed to update feed for {comic['name']}")
    
    logger.info(f"Feed update complete. Successfully updated {success_count}/{len(comics)} feeds.")

if __name__ == "__main__":
    update_all_feeds()