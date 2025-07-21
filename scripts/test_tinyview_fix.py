#!/usr/bin/env python3
"""
Test script to validate TinyView scraper fixes work locally.
This helps us verify the fixes before pushing to GitHub Actions.
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper

# Set up logging to see detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_firefox_setup():
    """Test if Firefox WebDriver can be set up successfully."""
    print("=== Testing Firefox WebDriver Setup ===")
    scraper = TinyviewScraper()
    try:
        scraper.setup_driver()
        print("✅ Firefox WebDriver setup successful")
        return True
    except Exception as e:
        print(f"❌ Firefox WebDriver setup failed: {e}")
        return False
    finally:
        scraper.close_driver()

def test_comic_scraping():
    """Test scraping a known comic."""
    print("\n=== Testing Comic Scraping ===")
    scraper = TinyviewScraper()
    
    try:
        # Test with a recent date for a known comic
        test_date = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
        print(f"Testing with date: {test_date}")
        
        result = scraper.scrape_comic('lunarbaboon', test_date)
        if result:
            print(f"✅ Successfully scraped Lunarbaboon:")
            print(f"   Title: {result.get('title')}")
            print(f"   Images found: {result.get('image_count', 0)}")
            print(f"   URL: {result.get('url')}")
            return True
        else:
            print("⚠️  No comic data returned (may be normal if no comic published)")
            return None  # Not necessarily a failure
    except Exception as e:
        print(f"❌ Comic scraping failed: {e}")
        return False
    finally:
        scraper.close_driver()

def main():
    """Run all tests."""
    print("TinyView Scraper Fix Test")
    print("=" * 40)
    
    # Test Firefox setup
    firefox_ok = test_firefox_setup()
    
    if firefox_ok:
        # Test comic scraping
        scraping_result = test_comic_scraping()
        
        if scraping_result is True:
            print("\n🎉 All tests passed! TinyView scraper should work in GitHub Actions.")
        elif scraping_result is None:
            print("\n⚠️  Firefox setup works, but no comics found (this may be normal).")
            print("   The scraper infrastructure is working correctly.")
        else:
            print("\n❌ Comic scraping failed. Need to investigate further.")
    else:
        print("\n❌ Firefox setup failed. This needs to be fixed first.")

if __name__ == "__main__":
    main()