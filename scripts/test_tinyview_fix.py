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
        logger.exception("Full error details:")
        return False
    finally:
        scraper.close_driver()

def test_comic_scraping():
    """Test scraping multiple comics with different dates."""
    print("\n=== Testing Comic Scraping ===")
    
    # Test cases: comic slug and recent dates
    test_cases = [
        ('lunarbaboon', 1),  # 1 day ago
        ('lunarbaboon', 2),  # 2 days ago  
        ('nick-anderson', 1),
        ('adhdinos', 1),
    ]
    
    success_count = 0
    
    for comic_slug, days_ago in test_cases:
        print(f"\n--- Testing {comic_slug} ---")
        scraper = TinyviewScraper()
        
        try:
            test_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y/%m/%d")
            print(f"Testing {comic_slug} for date: {test_date}")
            
            result = scraper.scrape_comic(comic_slug, test_date)
            if result:
                print(f"✅ Successfully scraped {comic_slug}:")
                print(f"   Title: {result.get('title')}")
                print(f"   Images found: {result.get('image_count', 0)}")
                print(f"   URL: {result.get('url')}")
                if result.get('images'):
                    print(f"   First image: {result['images'][0]['url']}")
                success_count += 1
            else:
                print(f"⚠️  No comic data for {comic_slug} on {test_date} (may be normal)")
        except Exception as e:
            print(f"❌ Error scraping {comic_slug}: {e}")
            logger.exception("Full error details:")
        finally:
            scraper.close_driver()
    
    return success_count > 0

def test_feed_generation():
    """Test the full feed generation process locally."""
    print("\n=== Testing Local Feed Generation ===")
    
    try:
        # Import the update script functionality
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        
        # Test with a single comic to save time
        from comiccaster.feed_generator import ComicFeedGenerator
        
        comic_info = {
            'name': 'Lunarbaboon',
            'slug': 'lunarbaboon', 
            'author': 'Christopher Grady',
            'url': 'https://tinyview.com/lunarbaboon',
            'source': 'tinyview'
        }
        
        # Try to scrape recent comics
        scraper = TinyviewScraper()
        entries = []
        
        # Check last 3 days
        for i in range(3):
            test_date = (datetime.now() - timedelta(days=i)).strftime("%Y/%m/%d")
            try:
                result = scraper.scrape_comic('lunarbaboon', test_date)
                if result:
                    entry = {
                        'title': result.get('title', f"Lunarbaboon - {result['date']}"),
                        'url': result['url'],
                        'pub_date': result['date'].replace('/', '-'),
                        'description': result.get('description', ''),
                        'image_url': result['images'][0]['url'] if result['images'] else '',
                        'images': result['images']
                    }
                    entries.append(entry)
                    print(f"✅ Found comic for {test_date}")
                else:
                    print(f"⚠️  No comic for {test_date}")
            except Exception as e:
                print(f"❌ Error on {test_date}: {e}")
        
        scraper.close_driver()
        
        # Generate feed
        if entries:
            feed_gen = ComicFeedGenerator(output_dir='test_feeds')
            os.makedirs('test_feeds', exist_ok=True)
            
            success = feed_gen.generate_feed(comic_info, entries)
            if success:
                print(f"✅ Generated test feed with {len(entries)} entries")
                print("   Check test_feeds/lunarbaboon.xml")
                return True
            else:
                print("❌ Feed generation failed")
        else:
            print("⚠️  No entries found, creating placeholder feed")
            # Test placeholder generation
            placeholder_entries = [{
                'title': f"Lunarbaboon - No Recent Updates",
                'url': comic_info['url'],
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'description': f"No recent comics found for Lunarbaboon. Check back later!",
                'image_url': '',
                'images': []
            }]
            
            feed_gen = ComicFeedGenerator(output_dir='test_feeds')
            os.makedirs('test_feeds', exist_ok=True)
            success = feed_gen.generate_feed(comic_info, placeholder_entries)
            if success:
                print("✅ Generated placeholder feed")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Feed generation test failed: {e}")
        logger.exception("Full error details:")
        return False

def main():
    """Run all tests."""
    print("TinyView Scraper Local Test Suite")
    print("=" * 50)
    
    # Test Firefox setup first
    if not test_firefox_setup():
        print("\n❌ Firefox setup failed. Please run: python scripts/setup_local_testing.py")
        return False
    
    # Test comic scraping
    if not test_comic_scraping():
        print("\n❌ Comic scraping failed. The scraper may have issues.")
        return False
    
    # Test feed generation  
    if not test_feed_generation():
        print("\n❌ Feed generation failed.")
        return False
    
    print("\n🎉 All local tests passed!")
    print("The TinyView scraper should work in GitHub Actions.")
    print("\nNext steps:")
    print("1. Check the generated test feed: test_feeds/lunarbaboon.xml")
    print("2. If everything looks good, the GitHub Actions should work")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)