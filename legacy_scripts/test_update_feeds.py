#!/usr/bin/env python3
"""
Test script for ComicCaster feeds
Tests feed generation with a small subset of comics
"""

import logging
from scripts.update_feeds import scrape_comic, update_feed

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test comics - a small subset for testing
TEST_COMICS = [
    {
        'name': 'Garfield',
        'author': 'Jim Davis',
        'url': 'https://www.gocomics.com/garfield',
        'slug': 'garfield'
    },
    {
        'name': 'Calvin and Hobbes',
        'author': 'Bill Watterson',
        'url': 'https://www.gocomics.com/calvinandhobbes',
        'slug': 'calvinandhobbes'
    },
    {
        'name': 'Peanuts',
        'author': 'Charles Schulz',
        'url': 'https://www.gocomics.com/peanuts',
        'slug': 'peanuts'
    }
]

def test_feed_generation():
    """Test feed generation with a small set of comics."""
    success_count = 0
    
    for comic in TEST_COMICS:
        logger.info(f"Testing feed generation for {comic['name']}...")
        
        # Try to scrape the comic
        metadata = scrape_comic(comic['slug'])
        if metadata:
            logger.info(f"Successfully scraped {comic['name']}")
            logger.info(f"Metadata: {metadata}")
            
            # Try to update the feed
            if update_feed(comic, metadata):
                success_count += 1
                logger.info(f"Successfully updated feed for {comic['name']}")
            else:
                logger.error(f"Failed to update feed for {comic['name']}")
        else:
            logger.error(f"Failed to scrape {comic['name']}")
    
    # Log summary
    logger.info(f"Updated {success_count} out of {len(TEST_COMICS)} test feeds")
    
if __name__ == '__main__':
    test_feed_generation() 