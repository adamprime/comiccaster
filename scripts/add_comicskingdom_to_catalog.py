#!/usr/bin/env python3
"""
Add all Comics Kingdom comics to the catalog.

This script:
1. Scrapes the full Comics Kingdom comics list (no authentication needed)
2. Categorizes comics as daily or political
3. Adds them to comics_list.json and political_comics_list.json
"""

import json
import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from typing import List, Dict


def fetch_page(url: str) -> BeautifulSoup:
    """Fetch a page and return BeautifulSoup object."""
    print(f"Fetching: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')


def extract_all_comics() -> List[Dict]:
    """Extract all comics from Comics Kingdom A-Z page."""
    soup = fetch_page('https://comicskingdom.com/features')
    
    comics = []
    
    # Find all comic links in the A-Z list
    # Links are in format: /comic-slug or /comic-slug/date
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        # Skip non-comic links
        if not href.startswith('/') or href in ['/', '/features', '/genre', '/subscribe']:
            continue
        
        # Extract comic name and slug
        comic_name = link.get_text(strip=True)
        if not comic_name:
            continue
        
        # Parse slug from href (remove leading slash and any date)
        parts = href.strip('/').split('/')
        slug = parts[0] if parts else None
        
        if not slug or len(slug) < 2:
            continue
        
        # Skip certain types
        if 'vintage' in slug.lower() or slug in ['genre', 'features', 'creator']:
            continue
        
        comics.append({
            'name': comic_name,
            'slug': slug,
            'url': f'https://comicskingdom.com/{slug}',
            'source': 'comicskingdom'
        })
    
    # Remove duplicates based on slug
    unique_comics = {}
    for comic in comics:
        slug = comic['slug']
        if slug not in unique_comics:
            unique_comics[slug] = comic
    
    comics = list(unique_comics.values())
    print(f"✅ Extracted {len(comics)} unique comics")
    
    return comics


def extract_political_cartoons() -> List[Dict]:
    """Extract political cartoons from Comics Kingdom."""
    soup = fetch_page('https://comicskingdom.com/genre/political')
    
    cartoons = []
    
    # Find all comic cards on the political page
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        # Political cartoons have links like /cartoonist-name
        if not href.startswith('/') or '?' in href:
            continue
        
        # Get the text content
        text = link.get_text(strip=True)
        
        # Look for cartoonist names (usually title case with spaces)
        if text and len(text) > 2 and not text.startswith('Read More'):
            # Parse slug
            parts = href.strip('/').split('/')
            slug = parts[0] if parts else None
            
            if slug and len(slug) > 2:
                cartoons.append({
                    'name': text,
                    'slug': slug,
                    'url': f'https://comicskingdom.com/{slug}',
                    'source': 'comicskingdom',
                    'is_political': True
                })
    
    # Remove duplicates
    unique_cartoons = {}
    for cartoon in cartoons:
        slug = cartoon['slug']
        if slug not in unique_cartoons:
            unique_cartoons[slug] = cartoon
    
    cartoons = list(unique_cartoons.values())
    print(f"✅ Extracted {len(cartoons)} political cartoons")
    
    return cartoons


def load_existing_comics(file_path: Path) -> List[Dict]:
    """Load existing comics from JSON file."""
    if not file_path.exists():
        print(f"⚠️  File not found: {file_path}")
        return []
    
    with open(file_path, 'r') as f:
        return json.load(f)


def merge_comics(existing: List[Dict], new_comics: List[Dict]) -> List[Dict]:
    """Merge new comics into existing list, avoiding duplicates."""
    # Create lookup by slug
    existing_slugs = {comic['slug']: comic for comic in existing}
    
    added_count = 0
    updated_count = 0
    
    for comic in new_comics:
        slug = comic['slug']
        
        if slug in existing_slugs:
            # Comic already exists - update source if needed
            if 'source' not in existing_slugs[slug]:
                existing_slugs[slug]['source'] = comic['source']
                updated_count += 1
        else:
            # New comic - add it
            # Get the highest position
            max_position = max([c.get('position', 0) for c in existing], default=0)
            
            comic['position'] = max_position + added_count + 1
            comic['is_updated'] = False
            
            existing_slugs[slug] = comic
            added_count += 1
    
    print(f"  Added: {added_count} new comics")
    print(f"  Updated: {updated_count} existing comics")
    
    # Convert back to list and sort by position
    merged = list(existing_slugs.values())
    merged.sort(key=lambda x: x.get('position', 999999))
    
    return merged


def save_comics_list(file_path: Path, comics: List[Dict]):
    """Save comics list to JSON file."""
    with open(file_path, 'w') as f:
        json.dump(comics, f, indent=2)
    print(f"✅ Saved to {file_path}")


def main():
    """Main function."""
    print("="*80)
    print("Comics Kingdom Catalog Integration")
    print("="*80)
    print()
    
    # Paths
    base_dir = Path(__file__).parent.parent
    daily_comics_file = base_dir / 'public' / 'comics_list.json'
    political_comics_file = base_dir / 'public' / 'political_comics_list.json'
    
    # Extract Comics Kingdom comics
    print("Step 1: Extracting all Comics Kingdom comics...")
    all_comics = extract_all_comics()
    print()
    
    print("Step 2: Extracting political cartoons...")
    political_cartoons = extract_political_cartoons()
    print()
    
    # Separate into categories
    # For now, treat all comics as daily unless they're in the political list
    political_slugs = {c['slug'] for c in political_cartoons}
    daily_comics = [c for c in all_comics if c['slug'] not in political_slugs]
    
    print(f"Categorized: {len(daily_comics)} daily comics, {len(political_cartoons)} political cartoons")
    print()
    
    # Load existing lists
    print("Step 3: Loading existing comics lists...")
    existing_daily = load_existing_comics(daily_comics_file)
    existing_political = load_existing_comics(political_comics_file)
    print(f"  Existing daily comics: {len(existing_daily)}")
    print(f"  Existing political cartoons: {len(existing_political)}")
    print()
    
    # Merge new comics
    print("Step 4: Merging Comics Kingdom comics into daily list...")
    merged_daily = merge_comics(existing_daily, daily_comics)
    print()
    
    print("Step 5: Merging Comics Kingdom cartoons into political list...")
    merged_political = merge_comics(existing_political, political_cartoons)
    print()
    
    # Save updated lists
    print("Step 6: Saving updated lists...")
    save_comics_list(daily_comics_file, merged_daily)
    save_comics_list(political_comics_file, merged_political)
    print()
    
    # Summary
    print("="*80)
    print("✅ SUCCESS!")
    print("="*80)
    print(f"Total daily comics: {len(merged_daily)} (+{len(merged_daily) - len(existing_daily)} from Comics Kingdom)")
    print(f"Total political cartoons: {len(merged_political)} (+{len(merged_political) - len(existing_political)} from Comics Kingdom)")
    print()
    print("Comics Kingdom comics are now available on the website!")
    print("Users can find them in the Daily Comics and Political Cartoons tabs.")
    print("="*80)
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
