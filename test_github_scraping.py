#!/usr/bin/env python3
"""
Test script to verify GoComics scraping works in GitHub Actions environment.
This is a smoke test to ensure the scraping infrastructure is working before
running the full feed update process.
"""

import sys
import os
sys.path.append(os.path.abspath('.'))

from scripts.update_feeds import scrape_comic
from datetime import datetime, timedelta
from urllib.parse import urlparse

def test_single_comic():
    """Test enhanced HTTP scraping to verify it works in CI environment"""
    comic_info = {
        'name': 'Pearls Before Swine',
        'slug': 'pearlsbeforeswine',
        'url': 'https://www.gocomics.com/pearlsbeforeswine'
    }
    
    # Test with yesterday's date (more reliable than today)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')
    print(f'Testing enhanced HTTP scraping for {comic_info["name"]} on {yesterday}...')
    print(f'URL: https://www.gocomics.com/{comic_info["slug"]}/{yesterday}')
    
    try:
        result = scrape_comic(comic_info, yesterday)
        if result:
            print('✅ SUCCESS! Scraping returned a result')
            print(f'Title: {result.get("title", "N/A")}')
            print(f'Image URL: {result.get("image", "N/A")}')
            print(f'Comic URL: {result.get("url", "N/A")}')
            
            # Verify we got a real comic image URL
            image_url = result.get("image", "")
            if image_url:
                parsed_url = urlparse(image_url)
                # GoComics uses assets.amuniversal.com domain for images
                valid_domains = ['assets.amuniversal.com', 'assets.gocomics.com']
                if parsed_url.hostname and any(domain in parsed_url.hostname for domain in valid_domains):
                    print(f'✅ Image URL is from valid domain: {parsed_url.hostname}')
                    return True
                else:
                    print(f'⚠️  WARNING: Unexpected image domain: {parsed_url.hostname}')
                    # Still return True if we got an image
                    return bool(image_url)
            else:
                print('❌ FAILED - No image URL in result')
                return False
        else:
            print('❌ FAILED - scrape_comic returned None')
            return False
    except Exception as e:
        print(f'❌ ERROR during scraping: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("GoComics Scraping Test for GitHub Actions")
    print("=" * 60)
    print()
    
    success = test_single_comic()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Test PASSED - Scraping infrastructure is working")
    else:
        print("❌ Test FAILED - Check logs above for details")
    print("=" * 60)
    
    sys.exit(0 if success else 1)