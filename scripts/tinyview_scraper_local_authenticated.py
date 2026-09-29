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
from comiccaster.tinyview_strips import canonical_strip_url


def load_comics_catalog():
    """Load TinyView comics from catalog."""
    catalog_path = Path('public/tinyview_comics_list.json')
    
    with open(catalog_path, 'r') as f:
        comics = json.load(f)
    
    print(f"📚 Loaded {len(comics)} TinyView comics from catalog")
    return comics


def load_existing_data(data_dir='data'):
    """Return the canonical address of every strip saved in any TinyView data file.

    A strip is recorded by its own address, never by its date: several strips can
    share a date (Kowal Comics' five-part "Bella" is all filed under 2026/09/24), and
    keying on the date skipped every sibling once one of them was saved.
    """
    data_path = Path(data_dir)
    recorded = set()

    # Every saved file counts, including tinyview_2025-11-16_backup.json, which
    # can only add addresses.
    json_files = sorted(data_path.glob('tinyview_*.json'))

    if not json_files:
        print("📭 No existing data files found")
        return recorded

    print(f"📂 Loading existing data from {len(json_files)} file(s)...")

    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            for comic in data:
                url = comic.get('url')
                if url:
                    recorded.add(canonical_strip_url(url))

        except Exception as e:
            print(f"  ⚠️  Error loading {json_file}: {e}")
            continue

    print(f"✅ Loaded {len(recorded)} recorded strip address(es)")

    return recorded


def scrape_comic_with_scraper(scraper, comic_slug, comic_name, days_back=15, recorded=None, feed_slug=None):
    """Scrape one series' listed strips that are not yet recorded, each by its own address.

    Args:
        scraper: TinyviewScraper instance
        comic_slug: The TinyView URL path slug (used for scraping)
        comic_name: Display name of the comic
        days_back: How many days to look back
        recorded: Canonical addresses of strips already saved
        feed_slug: The slug to use in output data (for feed generation). Defaults to comic_slug.

    Returns:
        (records, not_recorded): the saved-record dicts for newly scraped strips, and the
        addresses of listed strips that were attempted but not recorded (the page showed
        none of the strip's own panels, or scraping failed). The next run retries those.
    """
    if feed_slug is None:
        feed_slug = comic_slug
    recorded = recorded or set()

    results = []
    not_recorded = []

    try:
        print(f"  Fetching recent comics...")
        recent_comics = scraper.get_recent_comics(comic_slug, days_back=days_back)

        if not recent_comics:
            print(f"  ⚠️  No recent comics found")
            return results, not_recorded

        # One entry per strip: the listing can repeat a link (e.g. once more with
        # a #comments fragment), and the canonical address names the strip.
        listed = {}
        for comic_data in recent_comics:
            listed.setdefault(canonical_strip_url(comic_data['url']), comic_data)

        new_strips = [(address, data) for address, data in listed.items() if address not in recorded]
        skipped = len(listed) - len(new_strips)
        if skipped > 0:
            print(f"  ⏭️  Skipping {skipped} already-recorded strip(s)")

        if not new_strips:
            print(f"  ✅ All recent comics already scraped")
            return results, not_recorded

        print(f"  Found {len(new_strips)} new comic(s) to scrape")

        for address, comic_data in new_strips:
            try:
                print(f"    Scraping {address}...")
                result = scraper.scrape_comic(comic_slug, comic_data['date'], strip_url=address)

                if result:
                    # Convert to serializable format matching Comics Kingdom pattern
                    comic_json = {
                        'name': comic_name,
                        'slug': feed_slug,  # Use feed_slug for output (may differ from TinyView URL path)
                        'date': result['date'].replace('/', '-'),  # Convert to YYYY-MM-DD
                        'url': address,  # The listed address, not wherever the browser ended up
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
                    not_recorded.append(address)
                    print(f"    ⚠️  Failed to scrape")

            except Exception as e:
                not_recorded.append(address)
                print(f"    ❌ Error: {e}")
                continue

    except Exception as e:
        print(f"  ❌ Error: {e}")

    if not_recorded:
        print(f"  ⚠️  {len(not_recorded)} listed strip(s) not recorded:")
        for address in not_recorded:
            print(f"      {address}")

    return results, not_recorded


def scrape_all_comics_authenticated(comics, date_str, days_back=15, recorded=None):
    """Scrape all comics using one authenticated browser session.

    ``recorded`` is the set of canonical strip addresses already saved; those strips
    are not fetched again.
    """
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
        all_not_recorded = []
        
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
                results, not_recorded = scrape_comic_with_scraper(
                    scraper, tinyview_slug, name, days_back, recorded, feed_slug=slug)
                all_not_recorded.extend(not_recorded)
                
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
        # Every listed strip should end up recorded; anything named here is retried
        # by the next run. Operators grep this line to confirm a run captured all.
        print(f"Listed but not recorded: {len(all_not_recorded)}")
        for address in all_not_recorded:
            print(f"  {address}")
        print("=" * 80)
        
        return all_results
        
    finally:
        print("\nClosing browser...")
        driver.quit()


def merge_with_existing(output_file, new_strips):
    """Add this run's strips to the day's existing file, keyed by strip address.

    A same-day rerun must not erase what an earlier run saved (and a rerun that
    finds nothing must not leave ``[]`` behind for the count guard). The existing
    record wins for an address present in both.
    """
    if not output_file.exists():
        return new_strips
    try:
        with open(output_file) as f:
            existing = json.load(f)
        if not isinstance(existing, list):
            raise ValueError(f"expected a list of strips, got {type(existing).__name__}")
    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(f"⚠️  Could not read existing {output_file}: {e}; using this run's strips only")
        return new_strips

    existing_addresses = {
        canonical_strip_url(strip['url']) for strip in existing
        if isinstance(strip, dict) and strip.get('url')
    }
    added = [strip for strip in new_strips if canonical_strip_url(strip['url']) not in existing_addresses]
    merged = existing + added
    print(
        f"🔀 Merge: {len(existing)} already in {output_file.name} + "
        f"{len(added)} new = {len(merged)} total"
    )
    return merged


def main():
    parser = argparse.ArgumentParser(
        description='Scrape TinyView comics with authentication and save to JSON'
    )
    parser.add_argument('--date', help='Date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--days-back', type=int, default=90,
                       help='Number of days to look back (default: 90)')
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
    
    # Addresses of strips already saved, so they aren't scraped again
    recorded = load_existing_data(args.output_dir)
    
    # Scrape all comics (authenticated)
    results = scrape_all_comics_authenticated(comics, date_str, args.days_back, recorded)
    
    # Save to JSON file (matching Comics Kingdom pattern), adding to any earlier
    # run's strips for the same day
    output_file = output_dir / f'tinyview_{date_str}.json'
    results = merge_with_existing(output_file, results)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Saved {len(results)} comics to {output_file}")
    print(f"\n✅ Success! Data ready for GitHub Actions to process.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
