#!/usr/bin/env python3
"""
Test script to verify scraping works in GitHub Actions environment
"""

import sys
import os
sys.path.append(os.path.abspath('.'))

from scripts.update_feeds import scrape_comic
from datetime import datetime, timedelta

def test_single_comic():
    """Test enhanced HTTP scraping to verify it works"""
    comic_info = {
        'name': 'Pearls Before Swine',
        'slug': 'pearlsbeforeswine'
    }
    
    # Test with yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')
    print(f'Testing enhanced HTTP scraping for {comic_info["name"]} on {yesterday}...')
    
    try:
        result = scrape_comic(comic_info, yesterday)
        if result:
            print('✅ SUCCESS!')
            print(f'Title: {result["title"]}')
            print(f'Image URL: {result["image"]}')
            print(f'URL: {result["url"]}')
            
            # Verify we got a real comic image URL
            if 'featureassets.gocomics.com' in result["image"]:
                print('✅ Image URL looks valid (featureassets domain)')
                return True
            else:
                print('⚠️  WARNING: Image URL may not be a comic strip')
                return False
        else:
            print('❌ FAILED - No result returned')
            return False
    except Exception as e:
        print(f'❌ ERROR: {e}')
        return False

if __name__ == "__main__":
    success = test_single_comic()
    sys.exit(0 if success else 1)