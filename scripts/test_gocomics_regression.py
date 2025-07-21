#!/usr/bin/env python3
"""
Regression test to ensure GoComics scraping still works after Tinyview changes.
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.gocomics_scraper import GoComicsScraper
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_gocomics_daily_comics():
    """Test that daily GoComics feeds still work."""
    logger.info("=" * 60)
    logger.info("Testing GoComics Daily Comics")
    logger.info("=" * 60)
    
    # Test a few popular daily comics
    test_comics = [
        {'name': 'Garfield', 'slug': 'garfield'},
        {'name': 'Calvin and Hobbes', 'slug': 'calvinandhobbes'},
        {'name': 'Peanuts', 'slug': 'peanuts'}
    ]
    
    today = datetime.now()
    success_count = 0
    scraper = GoComicsScraper(source_type="gocomics-daily")
    
    for comic in test_comics:
        logger.info(f"\nTesting {comic['name']}...")
        
        try:
            # Test fetching today's comic
            date_str = today.strftime('%Y/%m/%d')
            result = scraper.scrape_comic(comic['slug'], date_str)
            
            if result and result.get('image_url'):
                logger.info(f"✅ {comic['name']}: Found image at {result['image_url']}")
                success_count += 1
            else:
                logger.error(f"❌ {comic['name']}: No image found")
                
        except Exception as e:
            logger.error(f"❌ {comic['name']}: Error - {e}")
    
    logger.info(f"\nDaily Comics Result: {success_count}/{len(test_comics)} passed")
    return success_count == len(test_comics)


def test_gocomics_political_comics():
    """Test that political GoComics feeds still work."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing GoComics Political Comics")
    logger.info("=" * 60)
    
    # Test a few political comics
    test_comics = [
        {'name': 'Doonesbury', 'slug': 'doonesbury'},
        {'name': 'The Boondocks', 'slug': 'theboondocks'},
        {'name': 'Non Sequitur', 'slug': 'nonsequitur'}
    ]
    
    today = datetime.now()
    success_count = 0
    scraper = GoComicsScraper(source_type="gocomics-political")
    
    for comic in test_comics:
        logger.info(f"\nTesting {comic['name']}...")
        
        try:
            # Test fetching today's comic
            date_str = today.strftime('%Y/%m/%d')
            result = scraper.scrape_comic(comic['slug'], date_str)
            
            if result and result.get('image_url'):
                logger.info(f"✅ {comic['name']}: Found image at {result['image_url']}")
                success_count += 1
            else:
                logger.error(f"❌ {comic['name']}: No image found")
                
        except Exception as e:
            logger.error(f"❌ {comic['name']}: Error - {e}")
    
    logger.info(f"\nPolitical Comics Result: {success_count}/{len(test_comics)} passed")
    return success_count == len(test_comics)


def test_feed_generation():
    """Test that feed generation still works for GoComics."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Feed Generation")
    logger.info("=" * 60)
    
    # Test generating a feed for Garfield
    comic_info = {
        'name': 'Garfield',
        'slug': 'garfield',
        'author': 'Jim Davis',
        'url': 'https://www.gocomics.com/garfield'
    }
    
    try:
        feed_gen = ComicFeedGenerator()
        
        # Create some test entries
        today = datetime.now()
        entries = []
        
        for i in range(3):
            date = today - timedelta(days=i)
            entries.append({
                'title': f"Garfield - {date.strftime('%B %d, %Y')}",
                'link': f"https://www.gocomics.com/garfield/{date.strftime('%Y/%m/%d')}",
                'date': date.strftime('%Y-%m-%d'),
                'description': 'Test comic strip',
                'image_url': 'https://assets.amuniversal.com/test.jpg'
            })
        
        # Generate the feed
        success = feed_gen.generate_feed(comic_info, entries)
        
        if success:
            logger.info("✅ Feed generation successful")
            
            # Check if file exists
            feed_path = f"public/feeds/{comic_info['slug']}.xml"
            if os.path.exists(feed_path):
                logger.info(f"✅ Feed file created at {feed_path}")
                return True
            else:
                logger.error(f"❌ Feed file not found at {feed_path}")
                return False
        else:
            logger.error("❌ Feed generation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Feed generation error: {e}")
        return False


def main():
    """Run all regression tests."""
    logger.info("Starting GoComics Regression Tests")
    logger.info("These tests ensure existing functionality still works\n")
    
    results = {
        'Daily Comics': test_gocomics_daily_comics(),
        'Political Comics': test_gocomics_political_comics(),
        'Feed Generation': test_feed_generation()
    }
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("REGRESSION TEST SUMMARY")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("\n🎉 All regression tests passed!")
    else:
        logger.error("\n⚠️  Some regression tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()