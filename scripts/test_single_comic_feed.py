#!/usr/bin/env python3
"""
Test the complete feed generation with the new approach for a single comic.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper
from comiccaster.feed_generator import ComicFeedGenerator

def test_full_pipeline():
    """Test the complete pipeline for a single comic."""
    print("Testing Full TinyView Pipeline")
    print("=" * 40)
    
    comic_info = {
        'name': 'Lunarbaboon',
        'slug': 'lunarbaboon',
        'author': 'Christopher Grady',
        'url': 'https://tinyview.com/lunarbaboon',
        'source': 'tinyview'
    }
    
    scraper = TinyviewScraper()
    entries = []
    
    try:
        # Step 1: Get recent comics
        print("Step 1: Finding recent comics...")
        recent_comics = scraper.get_recent_comics('lunarbaboon', days_back=15)
        print(f"✅ Found {len(recent_comics)} recent comics")
        
        # Step 2: Scrape each comic for details
        print("\nStep 2: Scraping comic details...")
        for i, comic_data in enumerate(recent_comics[:3]):  # Just test first 3
            print(f"  Scraping comic {i+1}: {comic_data['title']} ({comic_data['date']})")
            
            result = scraper.scrape_comic('lunarbaboon', comic_data['date'])
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
                print(f"    ✅ Success! Found {len(result['images'])} images")
            else:
                print(f"    ⚠️  No details found")
        
        print(f"\nStep 3: Generating RSS feed...")
        if entries:
            # Step 3: Generate feed
            feed_gen = ComicFeedGenerator(output_dir='test_feeds')
            os.makedirs('test_feeds', exist_ok=True)
            
            success = feed_gen.generate_feed(comic_info, entries)
            if success:
                print(f"✅ Generated RSS feed with {len(entries)} entries!")
                print("Check: test_feeds/lunarbaboon.xml")
                
                # Show a preview of what's in the feed
                print("\nFeed Preview:")
                for entry in entries:
                    print(f"  - {entry['title']}")
                    print(f"    Date: {entry['pub_date']}")
                    print(f"    Images: {len(entry['images'])}")
                    if entry['images']:
                        print(f"    First image: {entry['images'][0]['url'][:50]}...")
                    print()
                
                return True
            else:
                print("❌ Feed generation failed")
        else:
            print("❌ No entries to generate feed")
        
        return False
        
    finally:
        scraper.close_driver()

if __name__ == "__main__":
    success = test_full_pipeline()
    if success:
        print("🎉 Complete pipeline test successful!")
        print("The new approach should work perfectly in GitHub Actions!")
    else:
        print("❌ Pipeline test failed")