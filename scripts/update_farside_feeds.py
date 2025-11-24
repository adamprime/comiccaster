#!/usr/bin/env python3
"""
Update The Far Side RSS feeds.

This script updates both Far Side feeds:
1. Daily Dose - 5 rotating classic comics (updated daily)
2. New Stuff - New artwork by Gary Larson (sporadic updates)
"""

import sys
import os
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytz

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.scraper_factory import ScraperFactory
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_farside_comics():
    """Load The Far Side comics catalog."""
    catalog_path = Path('public/farside_comics_list.json')
    
    if not catalog_path.exists():
        logger.error(f"Far Side catalog not found: {catalog_path}")
        return []
    
    with open(catalog_path, 'r') as f:
        comics = json.load(f)
    
    logger.info(f"Loaded {len(comics)} Far Side comics from catalog")
    return comics


def update_daily_dose():
    """Update the Daily Dose feed."""
    logger.info("=" * 80)
    logger.info("Updating Far Side Daily Dose Feed")
    logger.info("=" * 80)
    
    scraper = ScraperFactory.get_scraper('farside-daily')
    feed_gen = ComicFeedGenerator(output_dir='public/feeds')
    
    # Get today's date in US/Eastern timezone (comics publish on Eastern time)
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    
    # The Far Side only keeps the last 3 days available (today + 2 days back)
    # Older dates redirect to today's page
    logger.info("Scraping last 3 days of Daily Dose comics...")
    
    all_comics = []
    for days_ago in range(2, -1, -1):  # 2 days ago, yesterday, today
        target_date = now_eastern - timedelta(days=days_ago)
        date_str = target_date.strftime('%Y/%m/%d')
        
        logger.info(f"  Scraping {date_str}...")
        result = scraper.scrape_daily_dose(date_str)
        
        if not result or 'comics' not in result:
            logger.warning(f"  Failed to scrape {date_str}")
            continue
        
        comics = result['comics']
        logger.info(f"  Found {len(comics)} comics for {date_str}")
        
        # Add date info to each comic
        for comic in comics:
            comic['target_date'] = target_date
            comic['date_str'] = date_str
        
        all_comics.extend(comics)
    
    if not all_comics:
        logger.error("Failed to scrape any comics")
        return False
    
    logger.info(f"Successfully scraped {len(all_comics)} total comics from last 3 days")
    
    # Create comic_info dict (metadata about the comic/feed)
    comic_info = {
        'name': 'The Far Side - Daily Dose',
        'slug': 'farside-daily',
        'author': 'Gary Larson',
        'url': 'https://www.thefarside.com/',
        'source': 'farside-daily'
    }
    
    # Prepare all comics as entries for the feed generator
    entries = []
    for i, comic in enumerate(all_comics):
        try:
            # Build description with image and caption
            description = f'<img src="{comic["image_url"]}" alt="The Far Side comic" style="max-width: 100%; height: auto;"/>'
            if comic.get('caption'):
                description += f'<p style="margin-top: 10px; font-style: italic;">{comic["caption"]}</p>'
            description += '<p style="margin-top: 15px; font-size: 0.9em;"><a href="https://www.thefarside.com/">Visit The Far Side</a> | © Gary Larson</p>'
            
            # Use 8am Eastern Time + minutes based on position
            pub_time = comic['target_date'].replace(hour=8, minute=i, second=0, microsecond=0)
            date_formatted = pub_time.strftime('%Y-%m-%d')
            
            # Create metadata for this comic
            # NOTE: Don't include 'image_url' - it causes description to be rebuilt
            # We already built the description with image + caption above
            entries.append({
                'title': f"The Far Side - {date_formatted} #{(i % 5) + 1}",
                'url': comic['url'],
                'description': description,
                'pub_date': pub_time.strftime('%a, %d %b %Y %H:%M:%S %z')
            })
        except Exception as e:
            logger.error(f"Error preparing comic: {e}")
            continue
    
    # Use generate_feed which handles multiple entries at once
    if feed_gen.generate_feed(comic_info, entries):
        logger.info(f"✅ Successfully generated feed with {len(entries)} comics")
        return True
    else:
        logger.error("Failed to generate feed")
        return False


def update_new_stuff():
    """Update the New Stuff feed."""
    logger.info("=" * 80)
    logger.info("Updating Far Side New Stuff Feed")
    logger.info("=" * 80)
    
    scraper = ScraperFactory.get_scraper('farside-new')
    feed_gen = ComicFeedGenerator(output_dir='public/feeds')
    
    # Load last known comic ID
    last_id_file = Path('data/farside_new_last_id.txt')
    last_known_id = 0
    
    if last_id_file.exists():
        try:
            with open(last_id_file, 'r') as f:
                last_known_id = int(f.read().strip())
            logger.info(f"Last known New Stuff comic ID: {last_known_id}")
        except:
            logger.warning("Could not read last comic ID, treating all as new")
    
    # Scrape New Stuff archive
    logger.info("Scraping New Stuff archive...")
    result = scraper.scrape_new_stuff()
    
    if not result or 'comics' not in result:
        logger.error("Failed to scrape New Stuff")
        return False
    
    all_comics = result['comics']
    logger.info(f"Found {len(all_comics)} total New Stuff comics")
    
    # Check if this is the initial population (last_known_id == 0 or feed doesn't exist)
    feed_path = Path('public/feeds/farside-new.xml')
    is_initial_population = (last_known_id == 0) or (not feed_path.exists())
    
    if is_initial_population:
        # Initial population: Add the most recent 10 comics to seed the feed
        logger.info("📝 Initial population: Adding recent New Stuff comics to feed")
        comics_to_detail = sorted(all_comics, key=lambda c: int(c['id']), reverse=True)[:10]
        logger.info(f"Will add {len(comics_to_detail)} recent comics to populate feed")
    else:
        # Normal operation: Only add NEW comics (ID > last_known_id)
        new_comics = [c for c in all_comics if int(c['id']) > last_known_id]
        
        if new_comics:
            logger.info(f"🎉 Found {len(new_comics)} NEW comics!")
            comics_to_detail = new_comics
        else:
            logger.info("No new comics found since last check")
            comics_to_detail = []
    
    # Scrape details for selected comics
    detailed_comics = []
    for comic in comics_to_detail:
        logger.info(f"Fetching details for comic {comic['id']}...")
        detail = scraper.scrape_new_stuff_detail(comic['url'])
        if detail:
            detailed_comics.append(detail)
    
    # Update last known ID
    if all_comics:
        max_id = max(int(c['id']) for c in all_comics)
        last_id_file.parent.mkdir(parents=True, exist_ok=True)
        with open(last_id_file, 'w') as f:
            f.write(str(max_id))
        logger.info(f"Updated last known ID to: {max_id}")
    
    # Create comic_info dict
    comic_info = {
        'name': 'The Far Side - New Stuff',
        'slug': 'farside-new',
        'author': 'Gary Larson',
        'url': 'https://www.thefarside.com/new-stuff',
        'source': 'farside-new'
    }
    
    # Generate feed entries
    # Use different dates for each comic to avoid duplicates (feed generator dedupes by date)
    from datetime import timedelta
    eastern = pytz.timezone('US/Eastern')
    base_time = datetime.now(eastern)  # Use Eastern timezone
    
    entries = []
    for i, comic in enumerate(detailed_comics):
        # Build description with image and caption
        description = f'<img src="{comic["image_url"]}" alt="{comic["title"]}" style="max-width: 100%; height: auto;"/>'
        if comic['caption']:
            description += f'<p style="margin-top: 10px;">{comic["caption"]}</p>'
        description += '<p style="margin-top: 15px; font-size: 0.9em;"><a href="https://www.thefarside.com/new-stuff">See all new work</a> | © Gary Larson</p>'
        
        # Give each comic a unique DATE (1 day apart) to avoid duplicates
        # Feed generator deduplicates by date, not datetime
        pub_time = base_time - timedelta(days=i)
        
        entries.append({
            'title': f"The Far Side - New Stuff: {comic['title']}",
            'url': comic['url'],
            'description': description,  # Already contains full HTML with image and caption
            'pub_date': pub_time.strftime('%a, %d %b %Y %H:%M:%S %z')
            # Note: Don't include 'image_url' - it would cause description to be rebuilt
        })
    
    # Generate and save feed
    try:
        success = feed_gen.generate_feed(comic_info, entries)
        
        if success:
            logger.info(f"✅ Successfully generated feed: public/feeds/farside-new.xml")
            return True
        else:
            logger.error("Failed to generate feed")
            return False
        
    except Exception as e:
        logger.error(f"Failed to generate feed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    logger.info("Starting Far Side feed update")
    
    # Update both feeds
    daily_success = update_daily_dose()
    new_success = update_new_stuff()
    
    logger.info("=" * 80)
    if daily_success and new_success:
        logger.info("✅ All Far Side feeds updated successfully!")
        return 0
    else:
        logger.error("❌ Some feeds failed to update")
        return 1


if __name__ == '__main__':
    sys.exit(main())
