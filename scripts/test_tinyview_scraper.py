#!/usr/bin/env python3
"""
Test the TinyviewScraper with real comics.

This script allows testing individual Tinyview comics to verify the scraper works correctly.
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path so we can import comiccaster
sys.path.insert(0, str(Path(__file__).parent.parent))

from comiccaster.tinyview_scraper import TinyviewScraper

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_comic(comic_slug: str, date: str = None):
    """Test scraping a specific comic."""
    if not date:
        # Default to yesterday (more likely to have content than today)
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y/%m/%d")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing comic: {comic_slug} for date: {date}")
    logger.info(f"{'='*60}")
    
    scraper = TinyviewScraper()
    
    try:
        result = scraper.scrape_comic(comic_slug, date)
        
        if result:
            logger.info(f"\n✅ Successfully scraped {comic_slug}!")
            logger.info(f"Title: {result.get('title', 'N/A')}")
            logger.info(f"Date: {result.get('date')}")
            logger.info(f"URL: {result.get('url')}")
            logger.info(f"Source: {result.get('source')}")
            logger.info(f"Image count: {result.get('image_count')}")
            
            if result.get('images'):
                logger.info("\nImages found:")
                for i, img in enumerate(result['images'], 1):
                    logger.info(f"  Image {i}:")
                    logger.info(f"    URL: {img['url']}")
                    logger.info(f"    Alt: {img.get('alt', 'N/A')}")
                    logger.info(f"    Title: {img.get('title', 'N/A')}")
            
            # Optionally save result to file for inspection
            output_file = f"test_results/{comic_slug}_{date.replace('/', '-')}.json"
            Path("test_results").mkdir(exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            logger.info(f"\nSaved result to: {output_file}")
            
        else:
            logger.error(f"\n❌ Failed to scrape {comic_slug} for date {date}")
            logger.error("This could mean:")
            logger.error("  - The comic doesn't exist")
            logger.error("  - No comic was published on this date")
            logger.error("  - The page structure has changed")
            logger.error("  - Network/timeout issues")
    
    except Exception as e:
        logger.error(f"\n❌ Error testing {comic_slug}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        scraper.close_driver()


def test_known_comics():
    """Test the known Tinyview comics."""
    known_comics = [
        'adhdinos',
        'nick-anderson'
    ]
    
    for comic_slug in known_comics:
        test_comic(comic_slug)
        print("\n")


def test_multiple_dates(comic_slug: str, num_days: int = 5):
    """Test a comic for multiple recent dates."""
    logger.info(f"\nTesting {comic_slug} for the last {num_days} days...")
    
    scraper = TinyviewScraper()
    successful_dates = []
    failed_dates = []
    
    try:
        for i in range(num_days):
            test_date = datetime.now() - timedelta(days=i)
            date_str = test_date.strftime("%Y/%m/%d")
            
            logger.info(f"\nTesting date: {date_str}")
            result = scraper.scrape_comic(comic_slug, date_str)
            
            if result:
                successful_dates.append(date_str)
                logger.info(f"✅ Success - found {result['image_count']} images")
            else:
                failed_dates.append(date_str)
                logger.info("❌ Failed - no comic found")
    
    finally:
        scraper.close_driver()
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Summary for {comic_slug}:")
    logger.info(f"Successful: {len(successful_dates)}/{num_days} days")
    logger.info(f"Failed: {len(failed_dates)}/{num_days} days")
    if successful_dates:
        logger.info(f"Latest successful date: {successful_dates[0]}")


def main():
    """Main function to run tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test the TinyviewScraper')
    parser.add_argument('comic', nargs='?', help='Comic slug to test (e.g., adhdinos)')
    parser.add_argument('--date', help='Date to test in YYYY/MM/DD format')
    parser.add_argument('--known', action='store_true', help='Test all known comics')
    parser.add_argument('--multi', type=int, help='Test multiple recent dates')
    
    args = parser.parse_args()
    
    if args.known:
        test_known_comics()
    elif args.comic:
        if args.multi:
            test_multiple_dates(args.comic, args.multi)
        else:
            test_comic(args.comic, args.date)
    else:
        # Interactive mode
        print("TinyView Comic Scraper Test")
        print("=" * 40)
        print("\nKnown comics:")
        print("  - adhdinos")
        print("  - nick-anderson")
        print("\nEnter 'all' to test all known comics")
        
        comic_slug = input("\nEnter comic slug to test: ").strip()
        
        if comic_slug.lower() == 'all':
            test_known_comics()
        else:
            use_custom_date = input("Use custom date? (y/n, default: yesterday): ").strip().lower()
            if use_custom_date == 'y':
                date = input("Enter date (YYYY/MM/DD): ").strip()
                test_comic(comic_slug, date)
            else:
                test_comic(comic_slug)


if __name__ == "__main__":
    main()