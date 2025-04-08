#!/usr/bin/env python3
"""
ComicCaster - Main script
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from comiccaster.loader import ComicsLoader
from comiccaster.scraper import ComicScraper
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="ComicCaster - Generate RSS feeds for GoComics")
    parser.add_argument('--comic', help='Comic slug to generate feed for')
    parser.add_argument('--all', action='store_true', help='Generate feeds for all comics')
    parser.add_argument('--output-dir', default='feeds', help='Output directory for feeds')
    args = parser.parse_args()

    if not args.comic and not args.all:
        parser.print_help()
        sys.exit(1)

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Initialize components
    loader = ComicsLoader()
    scraper = ComicScraper()
    feed_generator = ComicFeedGenerator(output_dir=args.output_dir)

    if args.comic:
        # Generate feed for a single comic
        comic = scraper.scrape_comic(args.comic)
        if comic:
            feed_generator.update_feed(comic)
            logger.info(f"Generated feed for {args.comic}")
        else:
            logger.error(f"Failed to scrape comic: {args.comic}")
    elif args.all:
        # Generate feeds for all comics
        comics = loader.load_comics_list()
        for comic in comics:
            try:
                comic_data = scraper.scrape_comic(comic['slug'])
                if comic_data:
                    feed_generator.update_feed(comic_data)
                    logger.info(f"Generated feed for {comic['slug']}")
                else:
                    logger.warning(f"Failed to scrape comic: {comic['slug']}")
            except Exception as e:
                logger.error(f"Error processing {comic['slug']}: {e}")

if __name__ == '__main__':
    main() 