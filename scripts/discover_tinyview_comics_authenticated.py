#!/usr/bin/env python3
"""
Discover all TinyView comics using authenticated session.
Compares with existing list and reports new comics.
"""

import sys
import os
import json
from pathlib import Path
from bs4 import BeautifulSoup
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from tinyview_scraper_secure import setup_driver, is_authenticated, load_config_from_env


def discover_all_comics_from_site(driver):
    """
    Discover all TinyView comics by browsing the site.
    Checks multiple pages: homepage, browse/all, user's followed comics, etc.
    """
    print(f"\n{'='*80}")
    print(f"Discovering all TinyView comics from the site")
    print("="*80)
    
    all_comics = {}
    
    # Method 1: Get from "All Series" page
    print("\n1. Checking 'All Series' page...")
    try:
        driver.get("https://tinyview.com/browse/all")
        import time
        time.sleep(3)
        
        # Scroll to load all comics
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all comic links
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            
            # Look for comic profile URLs: /comic-slug or tinyview.com/comic-slug
            if href.startswith('/') and href.count('/') == 1 and len(href) > 1:
                slug = href.strip('/')
                
                # Skip non-comic pages
                skip_pages = ['browse', 'notifications', 'about', 'terms', 'privacy', 
                             'signin', 'signup', 'user', 'settings', 'shop', 'search',
                             'discover', 'trending', 'new', 'popular', 'tinyview',
                             'terms-conditions', 'privacy-policy', 'contact', 'faq']
                if slug in skip_pages:
                    continue
                
                # Get comic name from link text or nearby elements
                name = link.get_text(strip=True)
                
                # If name is empty or too short, try parent elements
                if not name or len(name) < 2:
                    parent = link.parent
                    for _ in range(3):
                        if parent:
                            text = parent.get_text(strip=True)
                            if text and len(text) > 2 and len(text) < 100:
                                name = text
                                break
                            parent = parent.parent
                
                if name and slug not in all_comics:
                    # Clean up name
                    name = name.strip()
                    # Remove "published" and timestamps
                    name = re.sub(r'\s*published\s*', '', name, flags=re.IGNORECASE)
                    name = re.sub(r'\d+[hmd]\s*ago', '', name)
                    name = name.strip()
                    
                    if name and len(name) > 2:
                        all_comics[slug] = {
                            'name': name,
                            'slug': slug,
                            'url': f'https://tinyview.com/{slug}',
                            'source': 'tinyview'
                        }
                        print(f"   Found: {name} ({slug})")
        
        print(f"   Total from All Series: {len(all_comics)}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    # Method 2: Get from user's followed comics (if available)
    print("\n2. Checking user's followed comics...")
    try:
        # Try to get followed comics from profile or notifications
        driver.get("https://tinyview.com")
        import time
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Look in sidebar/navigation for followed comics
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            
            if href.startswith('/') and href.count('/') >= 1:
                slug = href.split('/')[1] if href.startswith('/') else href.strip('/').split('/')[0]
                
                # Skip if already found or is a known non-comic page
                if slug in all_comics or '/' in slug or slug in ['browse', 'notifications', 'user', 'signin']:
                    continue
                
                name = link.get_text(strip=True)
                if name and len(name) > 2 and slug:
                    # Clean up
                    name = re.sub(r'\s*published\s*', '', name, flags=re.IGNORECASE)
                    name = re.sub(r'\d+[hmd]\s*ago', '', name)
                    name = name.strip()
                    
                    if name and len(name) > 2 and slug not in all_comics:
                        all_comics[slug] = {
                            'name': name,
                            'slug': slug,
                            'url': f'https://tinyview.com/{slug}',
                            'source': 'tinyview'
                        }
                        print(f"   Found: {name} ({slug})")
        
        print(f"   Total discovered: {len(all_comics)}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    return list(all_comics.values())


def load_existing_comics():
    """Load current TinyView comics list."""
    comics_file = Path('public/tinyview_comics_list.json')
    
    if comics_file.exists():
        with open(comics_file, 'r') as f:
            comics = json.load(f)
        print(f"\n📚 Loaded {len(comics)} existing TinyView comics")
        return comics
    else:
        print("\n⚠️  No existing comics list found")
        return []


def compare_and_report(discovered, existing):
    """Compare discovered comics with existing list."""
    print(f"\n{'='*80}")
    print("COMPARISON RESULTS")
    print("="*80)
    
    existing_slugs = {c['slug'] for c in existing}
    discovered_slugs = {c['slug'] for c in discovered}
    
    # Find new comics
    new_slugs = discovered_slugs - existing_slugs
    new_comics = [c for c in discovered if c['slug'] in new_slugs]
    
    # Find missing comics (in our list but not found on site)
    missing_slugs = existing_slugs - discovered_slugs
    missing_comics = [c for c in existing if c['slug'] in missing_slugs]
    
    print(f"\nTotal discovered on site: {len(discovered)}")
    print(f"Total in our database: {len(existing)}")
    print(f"New comics found: {len(new_comics)}")
    print(f"Comics not found on site: {len(missing_slugs)}")
    
    if new_comics:
        print(f"\n{'='*80}")
        print("NEW COMICS TO ADD:")
        print("="*80)
        for comic in sorted(new_comics, key=lambda x: x['name']):
            print(f"  • {comic['name']}")
            print(f"    Slug: {comic['slug']}")
            print(f"    URL: {comic['url']}")
            print()
    
    if missing_slugs:
        print(f"\n{'='*80}")
        print("COMICS IN DATABASE BUT NOT FOUND ON SITE:")
        print("="*80)
        for comic in missing_comics:
            print(f"  • {comic['name']} ({comic['slug']})")
    
    return new_comics, missing_comics


def update_comics_list(existing, new_comics):
    """Add new comics to the list and save."""
    if not new_comics:
        print("\n✅ No new comics to add - list is up to date!")
        return False
    
    print(f"\n{'='*80}")
    print(f"UPDATING COMICS LIST")
    print("="*80)
    
    # Merge and sort
    all_comics = existing + new_comics
    all_comics = sorted(all_comics, key=lambda x: x['name'].lower())
    
    # Save to file
    comics_file = Path('public/tinyview_comics_list.json')
    with open(comics_file, 'w') as f:
        json.dump(all_comics, f, indent=2)
    
    print(f"✅ Updated {comics_file}")
    print(f"   Total comics: {len(all_comics)} ({len(new_comics)} added)")
    
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Discover new TinyView comics')
    parser.add_argument('--yes', '-y', action='store_true', help='Automatically add new comics without prompting')
    args = parser.parse_args()
    
    print("TinyView Comics Discovery Tool")
    print("="*80)
    
    # Load existing comics
    existing_comics = load_existing_comics()
    
    # Setup authenticated driver
    print("\nSetting up authenticated browser session...")
    driver = setup_driver(show_browser=False, use_profile=True)
    
    try:
        # Check authentication
        config = load_config_from_env()
        
        print("Checking authentication status...")
        if not is_authenticated(driver, wait_for_auth=True):
            print("\n❌ Not authenticated!")
            print("\nTo authenticate, run:")
            print("  python3 tinyview_scraper_secure.py --show-browser")
            driver.quit()
            return 1
        
        print("✅ Authenticated successfully!")
        
        # Discover all comics
        discovered_comics = discover_all_comics_from_site(driver)
        
        # Compare and report
        new_comics, missing_comics = compare_and_report(discovered_comics, existing_comics)
        
        # Ask user if they want to update
        if new_comics:
            print(f"\n{'='*80}")
            
            if args.yes:
                response = 'yes'
                print(f"Auto-adding {len(new_comics)} new comics (--yes flag)")
            else:
                try:
                    response = input(f"Add {len(new_comics)} new comics to the database? [Y/n]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nSkipping update")
                    response = 'n'
            
            if response in ['', 'y', 'yes']:
                if update_comics_list(existing_comics, new_comics):
                    print("\n🎉 Comics list updated successfully!")
                    print("\nNew comic feeds will be generated on the next update run.")
                    print("\nTo generate feeds immediately, run:")
                    print("  ./scripts/local_tinyview_update_authenticated.sh")
            else:
                print("\n⏭️  Skipped updating comics list")
        
        return 0
        
    finally:
        print("\nClosing browser...")
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
