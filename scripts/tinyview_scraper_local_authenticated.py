#!/usr/bin/env python3
"""
TinyView scraper for local execution with authentication.
Scrapes all TinyView comics using persistent Chrome profile and saves data to JSON.
Similar to Comics Kingdom workflow - saves raw data for GitHub Actions to process.
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add comiccaster to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from tinyview_scraper_secure import setup_driver, is_authenticated, load_config_from_env
from comiccaster.tinyview_scraper import TinyviewScraper


def load_comics_catalog():
    """Load TinyView comics from catalog."""
    catalog_path = Path('public/tinyview_comics_list.json')
    
    with open(catalog_path, 'r') as f:
        comics = json.load(f)
    
    print(f"📚 Loaded {len(comics)} TinyView comics from catalog")
    return comics


def load_existing_data(data_dir='data'):
    """Load all existing TinyView data files to avoid re-scraping."""
    data_path = Path(data_dir)
    existing_data = {}  # slug -> set of dates
    
    # Find all tinyview JSON files
    json_files = list(data_path.glob('tinyview_*.json'))
    
    if not json_files:
        print("📭 No existing data files found")
        return existing_data
    
    print(f"📂 Loading existing data from {len(json_files)} file(s)...")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            for comic in data:
                slug = comic.get('slug')
                date = comic.get('date')  # YYYY-MM-DD format
                
                if slug and date:
                    if slug not in existing_data:
                        existing_data[slug] = set()
                    existing_data[slug].add(date)
                    
        except Exception as e:
            print(f"  ⚠️  Error loading {json_file}: {e}")
            continue
    
    total_comics = sum(len(dates) for dates in existing_data.values())
    print(f"✅ Loaded {total_comics} existing comics across {len(existing_data)} series")
    
    return existing_data


def scrape_comic_with_scraper(scraper, comic_slug, comic_name, days_back=15, existing_dates=None, feed_slug=None):
    """Scrape a single comic using the authenticated TinyviewScraper.
    
    Args:
        scraper: TinyviewScraper instance
        comic_slug: The TinyView URL path slug (used for scraping)
        comic_name: Display name of the comic
        days_back: How many days to look back
        existing_dates: Set of dates already scraped
        feed_slug: The slug to use in output data (for feed generation). Defaults to comic_slug.
    """
    if feed_slug is None:
        feed_slug = comic_slug
    
    try:
        print(f"  Fetching recent comics...")
        recent_comics = scraper.get_recent_comics(comic_slug, days_back=days_back)
        
        if not recent_comics:
            print(f"  ⚠️  No recent comics found")
            return []
        
        # Filter out dates we already have
        if existing_dates:
            original_count = len(recent_comics)
            recent_comics = [
                c for c in recent_comics 
                if c['date'].replace('/', '-') not in existing_dates
            ]
            skipped = original_count - len(recent_comics)
            if skipped > 0:
                print(f"  ⏭️  Skipping {skipped} already-scraped comic(s)")
        
        if not recent_comics:
            print(f"  ✅ All recent comics already scraped")
            return []
        
        print(f"  Found {len(recent_comics)} new comic(s) to scrape")
        
        # Scrape each comic
        results = []
        for comic_data in recent_comics:
            try:
                print(f"    Scraping {comic_data['date']}...")
                result = scraper.scrape_comic(comic_slug, comic_data['date'])
                
                if result:
                    # Convert to serializable format matching Comics Kingdom pattern
                    comic_json = {
                        'name': comic_name,
                        'slug': feed_slug,  # Use feed_slug for output (may differ from TinyView URL path)
                        'date': result['date'].replace('/', '-'),  # Convert to YYYY-MM-DD
                        'url': result['url'],
                        'source': 'tinyview',
                        'images': result['images'],
                        'image_urls': [img['url'] for img in result['images']],  # Add for compatibility
                        'image_count': len(result['images']),
                        'description': result.get('description', ''),
                        'title': result.get('title', f"{comic_name} - {result['date']}")
                    }
                    results.append(comic_json)
                    print(f"    ✅ {len(result['images'])} image(s)")
                else:
                    print(f"    ⚠️  Failed to scrape")
                    
            except Exception as e:
                print(f"    ❌ Error: {e}")
                continue
        
        return results
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []


def scrape_all_comics_authenticated(comics, date_str, days_back=15, existing_data=None):
    """Scrape all comics using one authenticated browser session."""
    print(f"\n{'='*80}")
    print(f"Scraping {len(comics)} TinyView comics (authenticated)")
    print(f"Looking back {days_back} days from {date_str}")
    print("="*80)
    
    # Setup authenticated driver using persistent Chrome profile
    print("\nSetting up authenticated browser session...")
    driver = setup_driver(show_browser=False, use_profile=True)
    
    try:
        # Check if we're authenticated
        config = load_config_from_env()
        
        print("Checking authentication status...")
        if not is_authenticated(driver, wait_for_auth=True):
            print("\n❌ Not authenticated!")
            print("\nTo authenticate, run:")
            print("  python3 tinyview_scraper_secure.py --show-browser")
            print("\nThis will log you in and save the session to your Chrome profile.")
            driver.quit()
            sys.exit(1)
        
        print("✅ Authenticated successfully!")
        print("=" * 80 + "\n")
        
        # Create scraper with the authenticated driver
        scraper = TinyviewScraper()
        scraper.driver = driver  # Use the shared authenticated driver
        
        all_results = []
        
        for i, comic in enumerate(comics, 1):
            slug = comic['slug']
            name = comic['name']
            # Extract the actual TinyView URL path from the comic's URL
            # This handles cases where slug differs from URL (e.g., fowl-language-tinyview vs fowl-language)
            comic_url = comic.get('url', '')
            if comic_url:
                from urllib.parse import urlparse
                tinyview_slug = urlparse(comic_url).path.strip('/')
            else:
                tinyview_slug = slug
            
            print(f"[{i}/{len(comics)}] Scraping {name} ({tinyview_slug})...")
            
            try:
                # Get existing dates for this comic (use original slug for data tracking)
                existing_dates = existing_data.get(slug, set()) if existing_data else set()
                
                results = scrape_comic_with_scraper(scraper, tinyview_slug, name, days_back, existing_dates, feed_slug=slug)
                
                if results:
                    all_results.extend(results)
                    print(f"  ✅ Got {len(results)} new comic(s)")
                else:
                    print(f"  ⚠️  No new comics")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
        
        print(f"\n{'='*80}")
        print(f"Scraping Complete!")
        print(f"Total new comics scraped: {len(all_results)}")
        print("=" * 80)
        
        return all_results
        
    finally:
        print("\nClosing browser...")
        driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description='Scrape TinyView comics with authentication and save to JSON'
    )
    parser.add_argument('--date', help='Date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--days-back', type=int, default=15, 
                       help='Number of days to look back (default: 15)')
    parser.add_argument('--output-dir', default='data', 
                       help='Output directory for JSON files (default: data)')
    
    args = parser.parse_args()
    
    # Get date
    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load comics
    comics = load_comics_catalog()
    if not comics:
        print("❌ No comics loaded")
        sys.exit(1)
    
    # Load existing data to avoid re-scraping
    existing_data = load_existing_data(args.output_dir)
    
    # Scrape all comics (authenticated)
    results = scrape_all_comics_authenticated(comics, date_str, args.days_back, existing_data)
    
    # Save to JSON file (matching Comics Kingdom pattern)
    output_file = output_dir / f'tinyview_{date_str}.json'
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Saved {len(results)} comics to {output_file}")
    print(f"\n✅ Success! Data ready for GitHub Actions to process.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
