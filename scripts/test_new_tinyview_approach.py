#!/usr/bin/env python3
"""
Test script to validate the new TinyView scraping approach.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper

def test_new_approach():
    """Test the new get_recent_comics approach."""
    print("Testing New TinyView Scraping Approach")
    print("=" * 50)
    
    scraper = TinyviewScraper()
    
    try:
        # Test with Lunarbaboon 
        print("\n=== Testing Lunarbaboon ===")
        recent_comics = scraper.get_recent_comics('lunarbaboon', days_back=15)
        
        print(f"Found {len(recent_comics)} recent comics:")
        for comic in recent_comics[:5]:  # Show first 5
            print(f"  - {comic['date']}: {comic['title']} ({comic['url']})")
        
        if recent_comics:
            print(f"\n✅ Success! Found {len(recent_comics)} recent comics in the last 15 days")
            print("This should solve the 'no comics found' issue!")
        else:
            print("⚠️  No comics found in the last 15 days")
        
        # Test with Nick Anderson
        print("\n=== Testing Nick Anderson ===") 
        recent_comics_na = scraper.get_recent_comics('nick-anderson', days_back=15)
        
        print(f"Found {len(recent_comics_na)} recent comics:")
        for comic in recent_comics_na[:3]:  # Show first 3
            print(f"  - {comic['date']}: {comic['title']}")
        
        if recent_comics_na:
            print(f"✅ Success! Found {len(recent_comics_na)} recent comics")
        else:
            print("⚠️  No comics found")
        
        # Show total efficiency improvement
        total_found = len(recent_comics) + len(recent_comics_na)
        print(f"\n🎉 New approach found {total_found} comics total!")
        print("Old approach: Would have tried 15 dates per comic = 30 attempts")
        print(f"New approach: Only needed 2 main page fetches + {total_found} comic fetches")
        print(f"Efficiency gain: ~{100 - (total_found + 2) * 100 / 30:.0f}% fewer requests!")
        
    finally:
        scraper.close_driver()

if __name__ == "__main__":
    test_new_approach()