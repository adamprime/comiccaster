#!/usr/bin/env python3
"""
Debug script to understand what the TinyView scraper is seeing.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper
from bs4 import BeautifulSoup

def debug_comic_page(comic_slug, date_str):
    """Debug what we see on a TinyView comic page."""
    print(f"\n=== Debugging {comic_slug} on {date_str} ===")
    
    scraper = TinyviewScraper()
    try:
        scraper.setup_driver()
        
        # Navigate to the comic's main page
        comic_main_url = f"https://tinyview.com/{comic_slug}"
        print(f"Navigating to: {comic_main_url}")
        
        scraper.driver.get(comic_main_url)
        
        # Wait for page to load
        import time
        time.sleep(5)
        
        # Get page source and parse
        page_source = scraper.driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        print(f"Page title: {scraper.driver.title}")
        print(f"Current URL: {scraper.driver.current_url}")
        
        # Look for links that might contain dates
        all_links = soup.find_all('a', href=True)
        print(f"Found {len(all_links)} total links")
        
        date_like_links = []
        for link in all_links:
            href = link['href']
            if any(part in href for part in ['2025', '2024', date_str]):
                date_like_links.append(href)
                print(f"Date-like link: {href}")
        
        if not date_like_links:
            print("No date-like links found. Let's check what links we do have:")
            for i, link in enumerate(all_links[:10]):  # Show first 10 links
                print(f"  {i+1}. {link.get('href', 'No href')}")
        
        # Let's also check for images
        all_images = soup.find_all('img')
        print(f"\nFound {len(all_images)} images")
        
        tinyview_images = []
        for img in all_images:
            src = img.get('src', '')
            if 'tinyview' in src or 'cdn.' in src:
                tinyview_images.append(src)
                print(f"TinyView image: {src}")
        
        # Try to find comic-specific content
        print(f"\nLooking for content related to '{comic_slug}'...")
        comic_mentions = soup.find_all(text=lambda text: comic_slug.replace('-', ' ').title() in str(text) if text else False)
        print(f"Found {len(comic_mentions)} mentions of comic name")
        
        # Save page source for manual inspection
        debug_file = f"debug_{comic_slug}_{date_str.replace('/', '_')}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"\nSaved page source to: {debug_file}")
        
    finally:
        scraper.close_driver()

def main():
    """Run debug tests on different comics and dates."""
    print("TinyView Scraper Debug Tool")
    print("=" * 40)
    
    # Test different comics and dates
    test_cases = [
        ('lunarbaboon', '2025/07/15'),  # Older date
        ('lunarbaboon', '2025/07/01'),  # Beginning of month
        ('nick-anderson', '2025/07/15'),
        ('adhdinos', '2025/07/10'),
    ]
    
    for comic_slug, date_str in test_cases:
        debug_comic_page(comic_slug, date_str)

if __name__ == "__main__":
    main()