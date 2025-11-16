#!/usr/bin/env python3
"""
Generate RSS feeds for Comics Kingdom comics from scraped data.

This script:
1. Loads scraped Comics Kingdom data (JSON)
2. Loads comics list to see which comics need feeds
3. Generates/updates RSS feeds for Comics Kingdom comics
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import pytz
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from comiccaster.feed_generator import ComicFeedGenerator


def load_scraped_data(days_back: int = 10) -> Dict[str, List[Dict]]:
    """Load scraped Comics Kingdom data from multiple days and group by slug.
    
    Args:
        days_back: Number of days to load (default 10, like GoComics)
    
    Returns:
        Dict mapping slug -> list of comic entries (newest first)
    """
    data_dir = Path('data')
    data_files = sorted(data_dir.glob('comicskingdom_*.json'), reverse=True)
    
    if not data_files:
        print(f"❌ No Comics Kingdom data files found in data/")
        return {}
    
    # Load up to days_back most recent files
    files_to_load = data_files[:days_back]
    
    print(f"📂 Loading Comics Kingdom data from {len(files_to_load)} day(s)...")
    
    # Index by slug, with each slug containing a list of entries (one per day)
    indexed = {}
    total_loaded = 0
    
    for data_file in files_to_load:
        date_from_file = data_file.stem.replace('comicskingdom_', '')
        
        try:
            with open(data_file, 'r') as f:
                comics = json.load(f)
            
            for comic in comics:
                slug = comic.get('slug')
                if slug:
                    if slug not in indexed:
                        indexed[slug] = []
                    indexed[slug].append(comic)
                    total_loaded += 1
            
            print(f"  ✅ {date_from_file}: {len(comics)} comics")
        except Exception as e:
            print(f"  ⚠️  Error loading {data_file.name}: {e}")
    
    print(f"✅ Loaded {total_loaded} total entries for {len(indexed)} unique comics")
    return indexed


def load_comics_list() -> List[Dict]:
    """Load Comics Kingdom comics from catalog."""
    comics_file = Path('public/comics_list.json')
    
    with open(comics_file, 'r') as f:
        all_comics = json.load(f)
    
    # Filter for Comics Kingdom comics
    ck_comics = [c for c in all_comics if c.get('source') == 'comicskingdom']
    
    print(f"✅ Found {len(ck_comics)} Comics Kingdom comics in catalog")
    return ck_comics


def generate_feed_for_comic(comic_info: Dict, scraped_data: Dict[str, List[Dict]], generator: ComicFeedGenerator) -> bool:
    """Generate/update feed for a single comic with multiple days of entries."""
    slug = comic_info['slug']
    
    # Check if we have scraped data for this comic
    if slug not in scraped_data:
        print(f"  ⚠️  No scraped data for {slug}")
        return False
    
    # Get all entries for this comic (from multiple days)
    comic_entries = scraped_data[slug]
    
    # Create feed entries for each day
    entries = []
    for scraped_comic in comic_entries:
        # Handle both single and multiple images per day
        images = []
        if 'image_urls' in scraped_comic:
            # Multiple images
            for i, url in enumerate(scraped_comic['image_urls']):
                images.append({
                    'url': url,
                    'alt': f"{comic_info['name']} - Panel {i+1}"
                })
        elif 'image_url' in scraped_comic:
            # Single image
            images.append({
                'url': scraped_comic['image_url'],
                'alt': comic_info['name']
            })
        else:
            # Skip entries with no images
            continue
        
        # Create feed entry from scraped data
        entry = {
            'title': f"{comic_info['name']} - {scraped_comic['date']}",
            'url': scraped_comic['url'],
            'images': images,  # Support multiple images
            'pub_date': datetime.strptime(scraped_comic['date'], '%Y-%m-%d').replace(tzinfo=pytz.UTC),
            'description': f"Comic strip for {scraped_comic['date']}",
            'id': scraped_comic['url']
        }
        entries.append(entry)
    
    if not entries:
        print(f"  ⚠️  No valid entries for {slug}")
        return False
    
    # Generate/update feed with ALL entries (multiple days)
    try:
        success = generator.generate_feed(comic_info, entries)
        if success:
            print(f"  ✅ {comic_info['name']} ({len(entries)} days)")
            return True
        else:
            print(f"  ❌ Failed: {comic_info['name']}")
            return False
    except Exception as e:
        print(f"  ❌ Error generating feed for {comic_info['name']}: {e}")
        return False


def main():
    """Main function."""
    print("="*80)
    print("Comics Kingdom Feed Generator")
    print("="*80)
    print()
    
    # Load scraped data
    print("Step 1: Loading scraped Comics Kingdom data...")
    scraped_data = load_scraped_data()
    if not scraped_data:
        print("❌ No scraped data available. Run scraper first:")
        print("   python comicskingdom_scraper_secure.py")
        return 1
    print()
    
    # Load comics list
    print("Step 2: Loading Comics Kingdom comics from catalog...")
    comics_list = load_comics_list()
    if not comics_list:
        print("❌ No Comics Kingdom comics in catalog")
        return 1
    print()
    
    # Initialize feed generator
    print("Step 3: Generating feeds...")
    generator = ComicFeedGenerator(
        base_url="https://comicskingdom.com",
        output_dir="public/feeds"
    )
    
    successful = 0
    failed = 0
    
    for comic in comics_list:
        if generate_feed_for_comic(comic, scraped_data, generator):
            successful += 1
        else:
            failed += 1
    
    print()
    print("="*80)
    print("✅ Feed Generation Complete!")
    print("="*80)
    print(f"Successful: {successful}")
    print(f"Skipped (no data): {failed}")
    print(f"Total: {len(comics_list)}")
    print()
    if failed > 0:
        print(f"ℹ️  {failed} comics skipped - no updates today or not favorited on Comics Kingdom")
        print()
    print("Feeds saved to: public/feeds/")
    print("="*80)
    
    # Always exit successfully - missing data is expected for comics that didn't update
    # or aren't favorited on the Comics Kingdom website
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
