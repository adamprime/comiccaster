#!/usr/bin/env python3
"""
Generate TinyView RSS feeds from pre-scraped JSON data.
Reads from data/tinyview_*.json files and generates feeds.
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def find_latest_tinyview_data():
    """Find the most recent TinyView data file."""
    data_dir = Path('data')
    
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return None
    
    # Find all tinyview JSON files
    tinyview_files = list(data_dir.glob('tinyview_*.json'))
    
    if not tinyview_files:
        logger.warning("No TinyView data files found in data/")
        return None
    
    # Sort by filename (which includes date) and get the latest
    latest_file = sorted(tinyview_files)[-1]
    logger.info(f"Found latest TinyView data: {latest_file}")
    
    return latest_file


def load_tinyview_data(data_file):
    """Load TinyView data from JSON file."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Loaded {len(data)} comics from {data_file}")
        return data
    except Exception as e:
        logger.error(f"Error loading data from {data_file}: {e}")
        return None


def load_tinyview_comics_list():
    """Load TinyView comics metadata."""
    comics_list_path = Path('public/tinyview_comics_list.json')
    
    try:
        with open(comics_list_path, 'r') as f:
            comics = json.load(f)
        
        # Create lookup dictionary by slug
        comics_dict = {comic['slug']: comic for comic in comics}
        logger.info(f"Loaded metadata for {len(comics_dict)} TinyView comics")
        
        return comics_dict
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
        return {}


def group_comics_by_slug(comics_data):
    """Group comics by slug."""
    grouped = {}
    
    for comic in comics_data:
        slug = comic['slug']
        if slug not in grouped:
            grouped[slug] = []
        grouped[slug].append(comic)
    
    # Sort each group by date (newest first)
    for slug in grouped:
        grouped[slug].sort(key=lambda x: x['date'], reverse=True)
    
    return grouped


def generate_feed_for_comic(comic_slug, comic_entries, comic_metadata):
    """Generate RSS feed for a single comic."""
    try:
        # Get comic info from metadata
        if comic_slug not in comic_metadata:
            logger.warning(f"No metadata found for {comic_slug}, skipping")
            return False
        
        comic_info = comic_metadata[comic_slug].copy()
        comic_info['source'] = 'tinyview'
        
        # Convert entries to feed format
        feed_entries = []
        for entry in comic_entries:
            feed_entry = {
                'title': entry.get('name', f"{comic_info['name']} - {entry['date']}"),
                'url': entry['url'],
                'pub_date': entry['date'].replace('/', '-'),
                'description': entry.get('description', ''),
                'image_url': entry['images'][0]['url'] if entry['images'] else '',
                'images': entry['images']
            }
            feed_entries.append(feed_entry)
        
        # Generate the feed
        feed_gen = ComicFeedGenerator(output_dir='public/feeds')
        success = feed_gen.generate_feed(comic_info, feed_entries)
        
        if success:
            logger.info(f"Generated feed for {comic_info['name']} at public/feeds/{comic_slug}.xml with {len(feed_entries)} entries")
            return True
        else:
            logger.error(f"Failed to generate feed for {comic_info['name']}")
            return False
            
    except Exception as e:
        logger.error(f"Error generating feed for {comic_slug}: {e}")
        return False


def main():
    """Main function to generate all TinyView feeds."""
    logger.info("=" * 80)
    logger.info("TinyView Feed Generation")
    logger.info("=" * 80)
    
    # Find latest data file
    data_file = find_latest_tinyview_data()
    if not data_file:
        logger.error("No TinyView data files found. Run tinyview_scraper_local.py first.")
        logger.info("\n⚠️  Skipping TinyView feed generation")
        return 0  # Exit successfully (don't fail the workflow)
    
    # Load data
    comics_data = load_tinyview_data(data_file)
    if not comics_data:
        logger.error("Failed to load TinyView data")
        return 0  # Exit successfully
    
    # Load comics metadata
    comics_metadata = load_tinyview_comics_list()
    if not comics_metadata:
        logger.error("Failed to load TinyView comics metadata")
        return 0  # Exit successfully
    
    # Group comics by slug
    grouped_comics = group_comics_by_slug(comics_data)
    logger.info(f"\nGenerating feeds for {len(grouped_comics)} TinyView comics...")
    
    # Generate feeds
    success_count = 0
    skipped_count = 0
    
    for slug, entries in grouped_comics.items():
        print(f"  Processing {slug}...", end=' ')
        
        if slug not in comics_metadata:
            print(f"⚠️  No metadata")
            skipped_count += 1
            continue
        
        if generate_feed_for_comic(slug, entries, comics_metadata):
            print(f"✅ {comics_metadata[slug]['name']}")
            success_count += 1
        else:
            print(f"❌ Failed")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("✅ Feed Generation Complete!")
    logger.info("=" * 80)
    logger.info(f"Successful: {success_count}")
    logger.info(f"Skipped (no data): {skipped_count}")
    logger.info(f"Total: {len(grouped_comics)}")
    logger.info(f"\nFeeds saved to: public/feeds/")
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
