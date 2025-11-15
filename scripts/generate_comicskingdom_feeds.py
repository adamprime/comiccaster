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


def load_scraped_data(date_str: str = None) -> Dict[str, Dict]:
    """Load scraped Comics Kingdom data and index by slug."""
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    data_file = Path('data') / f'comicskingdom_{date_str}.json'
    
    # If today's data doesn't exist, find the most recent data file
    if not data_file.exists():
        print(f"⚠️  No scraped data found for {date_str}, looking for most recent...")
        data_dir = Path('data')
        data_files = sorted(data_dir.glob('comicskingdom_*.json'), reverse=True)
        
        if not data_files:
            print(f"❌ No Comics Kingdom data files found in data/")
            return {}
        
        data_file = data_files[0]
        # Extract date from filename
        date_from_file = data_file.stem.replace('comicskingdom_', '')
        print(f"ℹ️  Using most recent data from {date_from_file}")
    
    with open(data_file, 'r') as f:
        comics = json.load(f)
    
    # Index by slug
    indexed = {}
    for comic in comics:
        slug = comic.get('slug')
        if slug:
            indexed[slug] = comic
    
    print(f"✅ Loaded {len(indexed)} comics from {data_file.name}")
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


def generate_feed_for_comic(comic_info: Dict, scraped_data: Dict, generator: ComicFeedGenerator) -> bool:
    """Generate/update feed for a single comic."""
    slug = comic_info['slug']
    
    # Check if we have scraped data for this comic
    if slug not in scraped_data:
        print(f"  ⚠️  No scraped data for {slug}")
        return False
    
    scraped_comic = scraped_data[slug]
    
    # Handle both single and multiple images per day
    # Some comics (like Six Chix) have multiple panels
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
        print(f"  ⚠️  No images found for {slug}")
        return False
    
    # Create feed entry from scraped data
    entry = {
        'title': f"{comic_info['name']} - {scraped_comic['date']}",
        'url': scraped_comic['url'],
        'images': images,  # Support multiple images
        'pub_date': datetime.strptime(scraped_comic['date'], '%Y-%m-%d').replace(tzinfo=pytz.UTC),
        'description': f"Comic strip for {scraped_comic['date']}",
        'id': scraped_comic['url']
    }
    
    # Generate/update feed with this entry
    try:
        success = generator.generate_feed(comic_info, [entry])
        if success:
            print(f"  ✅ {comic_info['name']}")
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
    print(f"Failed: {failed}")
    print(f"Total: {len(comics_list)}")
    print()
    print("Feeds saved to: public/feeds/")
    print("="*80)
    
    return 0 if failed == 0 else 1


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
