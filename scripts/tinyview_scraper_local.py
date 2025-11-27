#!/usr/bin/env python3
"""
TinyView scraper for local execution.
Scrapes all TinyView comics and saves data to JSON.
Much faster than running in GitHub Actions.
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse

# Add comiccaster to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comiccaster.tinyview_scraper import TinyviewScraper


def load_comics_catalog():
    """Load TinyView comics from catalog."""
    catalog_path = Path('public/tinyview_comics_list.json')
    
    with open(catalog_path, 'r') as f:
        comics = json.load(f)
    
    print(f"📚 Loaded {len(comics)} TinyView comics from catalog")
    return comics


def scrape_comic_with_scraper(scraper, comic_slug, days_back=15):
    """Scrape a single comic using the TinyviewScraper."""
    try:
        print(f"  Fetching recent comics...")
        recent_comics = scraper.get_recent_comics(comic_slug, days_back=days_back)
        
        if not recent_comics:
            print(f"  ⚠️  No recent comics found")
            return []
        
        print(f"  Found {len(recent_comics)} recent comics")
        
        # Scrape each comic
        results = []
        for comic_data in recent_comics:
            try:
                print(f"    Scraping {comic_data['date']}...")
                result = scraper.scrape_comic(comic_slug, comic_data['date'])
                
                if result:
                    # Convert to serializable format
                    comic_json = {
                        'name': result.get('title', comic_slug),
                        'slug': comic_slug,
                        'date': result['date'],
                        'url': result['url'],
                        'source': 'tinyview',
                        'images': result['images'],
                        'description': result.get('description', '')
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


def scrape_all_comics(comics, date_str, days_back=15):
    """Scrape all comics."""
    print(f"\n{'='*80}")
    print(f"Scraping {len(comics)} TinyView comics")
    print(f"Looking back {days_back} days from {date_str}")
    print("="*80)
    
    all_results = {}
    scraper = TinyviewScraper()
    
    try:
        for i, comic in enumerate(comics, 1):
            slug = comic['slug']
            name = comic['name']
            
            print(f"\n[{i}/{len(comics)}] Scraping {name} ({slug})...")
            
            try:
                results = scrape_comic_with_scraper(scraper, slug, days_back)
                
                if results:
                    all_results[slug] = results
                    print(f"  ✅ Scraped {len(results)} comic(s)")
                else:
                    print(f"  ⚠️  No comics found")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
            
            # Small delay between comics
            time.sleep(1)
    
    finally:
        scraper.close_driver()
    
    # Flatten results for saving
    flattened_results = []
    for slug, comic_list in all_results.items():
        flattened_results.extend(comic_list)
    
    print(f"\n✅ Successfully scraped {len(flattened_results)} total comics from {len(all_results)} series")
    return flattened_results


def main():
    parser = argparse.ArgumentParser(
        description='TinyView scraper - runs locally and saves data to JSON'
    )
    parser.add_argument('--date', help='Date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--output-dir', default='data', help='Output directory for JSON files')
    parser.add_argument('--days-back', type=int, default=15, help='Days to look back for comics')
    
    args = parser.parse_args()
    
    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load comics catalog
    comics = load_comics_catalog()
    
    # Scrape all comics
    results = scrape_all_comics(comics, date_str, days_back=args.days_back)
    
    if not results:
        print("⚠️  No comics scraped")
        return 1
    
    # Save results
    output_file = output_dir / f'tinyview_{date_str}.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*80}")
    print(f"✅ SUCCESS! Scraped {len(results)} comics")
    print(f"💾 Saved to {output_file}")
    print(f"{'='*80}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
