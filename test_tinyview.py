#!/usr/bin/env python3
"""
Test script for Tinyview scraper
Run this to test the Tinyview scraping functionality
"""

from datetime import datetime, timedelta
from comiccaster.tinyview_scraper import TinyviewScraper
import logging

# Set up more verbose logging for testing
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_tinyview_scraper():
    """Test the Tinyview scraper with different comics."""
    scraper = TinyviewScraper()
    
    # Test dates - try a few recent dates
    test_dates = [
        "2025/01/17",
        "2025/01/16", 
        "2025/01/15",
        "2025/01/14"
    ]
    
    print("=" * 80)
    print("TESTING TINYVIEW SCRAPER")
    print("=" * 80)
    
    # Test 1: Nick Anderson (single image)
    print("\n1. Testing Nick Anderson (single image comic)")
    print("-" * 40)
    
    for date in test_dates:
        print(f"\nTrying date: {date}")
        result = scraper.scrape_comic('nick-anderson', date)
        
        if result:
            print(f"✓ SUCCESS!")
            print(f"  Title: {result.get('title')}")
            print(f"  URL: {result.get('url')}")
            print(f"  Images found: {result.get('image_count')}")
            if result.get('image_url'):
                print(f"  Image: {result.get('image_url')}")
            break
        else:
            print(f"✗ No comic found for {date}")
    
    # Test 2: ADHDinos (multiple images possible)
    print("\n\n2. Testing ADHDinos (potentially multiple images)")
    print("-" * 40)
    
    # For ADHDinos, we might need to know the title slug
    # Let's try with generic 'cartoon' first
    for date in test_dates:
        print(f"\nTrying date: {date}")
        
        # Try different possible title slugs
        title_slugs = ['cartoon', 'comic', 'strip', 'update']
        
        for title_slug in title_slugs:
            print(f"  Trying title slug: {title_slug}")
            result = scraper.scrape_comic('adhdinos', date, title_slug)
            
            if result and result.get('image_count', 0) > 0:
                print(f"✓ SUCCESS with title slug '{title_slug}'!")
                print(f"  Title: {result.get('title')}")
                print(f"  URL: {result.get('url')}")
                print(f"  Images found: {result.get('image_count')}")
                
                for i, img in enumerate(result.get('images', [])):
                    print(f"  Image {i+1}: {img['url']}")
                break
        
        if result and result.get('image_count', 0) > 0:
            break
    
    # Test 3: Try to understand URL patterns
    print("\n\n3. URL Pattern Analysis")
    print("-" * 40)
    print("Based on the tests, Tinyview URL patterns appear to be:")
    print("  https://tinyview.com/{comic-slug}/{YYYY}/{MM}/{DD}/{title-slug}")
    print("\nWhere:")
    print("  - comic-slug: e.g., 'nick-anderson', 'adhdinos'")
    print("  - Date format: YYYY/MM/DD")
    print("  - title-slug: varies by comic, often 'cartoon'")
    
    scraper.close_driver()
    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_tinyview_scraper()