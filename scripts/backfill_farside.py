#!/usr/bin/env python3
"""
Backfill The Far Side Daily Dose feed with historical comics.
"""

import sys
import os
import time
import feedparser
from datetime import datetime, timedelta
from pathlib import Path
import pytz

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.scraper_factory import ScraperFactory
from comiccaster.feed_generator import ComicFeedGenerator

def backfill_days(num_days=10):
    """Backfill the last N days of Far Side Daily Dose comics."""
    print(f"Backfilling last {num_days} days of The Far Side Daily Dose")
    print("=" * 80)
    
    eastern = pytz.timezone('US/Eastern')
    scraper = ScraperFactory.get_scraper('farside-daily')
    feed_gen = ComicFeedGenerator(output_dir='public/feeds')
    feed_path = Path('public/feeds/farside-daily.xml')
    
    comic_info = {
        'name': 'The Far Side - Daily Dose',
        'slug': 'farside-daily',
        'author': 'Gary Larson',
        'url': 'https://www.thefarside.com/',
        'source': 'farside-daily'
    }
    
    # Load existing entries
    existing_dates = set()
    if feed_path.exists():
        try:
            existing_feed = feedparser.parse(str(feed_path))
            print(f"\nLoaded existing feed with {len(existing_feed.entries)} entries")
            for entry in existing_feed.entries:
                try:
                    if hasattr(entry, 'published_parsed'):
                        pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        if pub_date.tzinfo is None:
                            pub_date = pytz.UTC.localize(pub_date)
                        existing_dates.add(pub_date.date())
                except Exception as e:
                    print(f"Error processing entry: {e}")
        except Exception as e:
            print(f"Error loading feed: {e}")
    
    # Collect all new entries to add
    all_new_entries = []
    now = datetime.now(eastern)
    
    for days_ago in range(num_days - 1, -1, -1):  # Go from oldest to newest
        target_date = now - timedelta(days=days_ago)
        date_str = target_date.strftime('%Y/%m/%d')
        date_obj = target_date.date()
        
        if date_obj in existing_dates:
            print(f"\n{date_str}: Already in feed, skipping")
            continue
        
        print(f"\n{date_str}: Scraping...")
        result = scraper.scrape_daily_dose(date_str)
        
        if not result or 'comics' not in result:
            print(f"  ❌ Failed")
            continue
        
        comics = result['comics']
        print(f"  ✅ Found {len(comics)} comics")
        
        # Create entries for this day
        for i, comic in enumerate(comics):
            description = f'<img src="{comic["image_url"]}" alt="The Far Side comic" style="max-width: 100%; height: auto;"/>'
            if comic['caption']:
                description += f'<p style="margin-top: 10px; font-style: italic;">{comic["caption"]}</p>'
            description += '<p style="margin-top: 15px; font-size: 0.9em;"><a href="https://www.thefarside.com/">Visit The Far Side</a> | © Gary Larson</p>'
            
            pub_time = target_date.replace(hour=8, minute=i, second=0, microsecond=0)
            date_formatted = pub_time.strftime('%Y-%m-%d')
            title = f"The Far Side - {date_formatted} #{i+1}"
            
            all_new_entries.append({
                'title': title,
                'url': comic['url'],
                'description': description,
                'pub_date': pub_time.strftime('%a, %d %b %Y %H:%M:%S %z'),
                'date': pub_time
            })
        
        time.sleep(0.5)  # Be nice to the server
    
    if not all_new_entries:
        print("\n✅ No new entries to add")
        return
    
    # Now rebuild feed with existing + new entries
    print(f"\n\nRebuilding feed with {len(all_new_entries)} new entries...")
    
    # Create new feed
    fg = feed_gen.create_feed(comic_info)
    
    # Add new entries newest to oldest for proper RSS order
    all_new_entries.sort(key=lambda x: x['date'], reverse=True)
    for entry_data in all_new_entries:
        # Reverse the individual day's comics so #5 appears before #1
        fe = feed_gen.create_entry(comic_info, entry_data)
        fg.add_entry(fe)
    
    # Add existing entries
    if feed_path.exists():
        existing_feed = feedparser.parse(str(feed_path))
        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=30)
        kept = 0
        for entry in existing_feed.entries:
            try:
                if hasattr(entry, 'published_parsed'):
                    pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if pub_date.tzinfo is None:
                        pub_date = pytz.UTC.localize(pub_date)
                    if pub_date >= cutoff_date:
                        # Re-create as feedgen entry
                        entry_dict = {
                            'title': entry.title,
                            'url': entry.link,
                            'description': entry.description if hasattr(entry, 'description') else '',
                            'pub_date': entry.published if hasattr(entry, 'published') else ''
                        }
                        fe = feed_gen.create_entry(comic_info, entry_dict)
                        fg.add_entry(fe)
                        kept += 1
            except Exception as e:
                print(f"Error re-adding entry: {e}")
        print(f"  Kept {kept} existing entries")
    
    # Save
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(feed_path))
    
    print("\n" + "=" * 80)
    print(f"✅ Backfill complete! Feed now has {len(all_new_entries) + (kept if 'kept' in locals() else 0)} total entries")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Backfill Far Side Daily Dose feed')
    parser.add_argument('--days', type=int, default=10, help='Number of days to backfill')
    args = parser.parse_args()
    
    backfill_days(args.days)
