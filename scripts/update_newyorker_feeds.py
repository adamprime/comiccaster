#!/usr/bin/env python3
"""
Update The New Yorker Daily Cartoon RSS feed.

This script:
1. Scrapes the New Yorker Daily Cartoon listing page
2. Fetches individual cartoon pages for high-res images and details
3. Generates/updates the RSS feed

Respects rate limiting and does not require authentication.
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
import pytz

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.newyorker_scraper import NewYorkerScraper
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_existing_data(data_dir: str = 'data') -> dict:
    """Load existing New Yorker data to avoid re-scraping.
    
    Returns:
        Dict mapping cartoon URLs to their data
    """
    data_path = Path(data_dir)
    existing = {}
    
    for json_file in sorted(data_path.glob('newyorker_*.json')):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            for cartoon in data.get('cartoons', []):
                url = cartoon.get('url')
                if url:
                    existing[url] = cartoon
        except Exception as e:
            logger.warning(f"Error loading {json_file}: {e}")
    
    logger.info(f"Loaded {len(existing)} existing cartoons from data files")
    return existing


def save_data(cartoons: list, data_dir: str = 'data'):
    """Save scraped cartoon data to JSON file.
    
    Args:
        cartoons: List of cartoon data dicts
        data_dir: Directory to save data files
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    
    eastern = pytz.timezone('US/Eastern')
    date_str = datetime.now(eastern).strftime('%Y-%m-%d')
    output_file = data_path / f'newyorker_{date_str}.json'
    
    data = {
        'scraped_at': datetime.now(pytz.UTC).isoformat(),
        'cartoons': cartoons
    }
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved {len(cartoons)} cartoons to {output_file}")


def generate_feed(cartoons: list, output_dir: str = 'public/feeds'):
    """Generate RSS feed from cartoon data.
    
    Args:
        cartoons: List of cartoon data dicts
        output_dir: Directory for feed output
    """
    feed_gen = ComicFeedGenerator(
        base_url="https://www.newyorker.com",
        output_dir=output_dir
    )
    
    # Comic info for feed metadata
    comic_info = {
        'name': 'Daily Cartoon',
        'slug': 'newyorker-daily-cartoon',
        'author': 'The New Yorker',
        'url': 'https://www.newyorker.com/cartoons/daily-cartoon',
        'source': 'newyorker',
    }
    
    # Build feed entries
    entries = []
    eastern = pytz.timezone('US/Eastern')
    
    for cartoon in cartoons:
        if not cartoon.get('image_url'):
            continue
        
        # Parse date and set time to noon Eastern (typical publish time)
        date_str = cartoon.get('date', datetime.now(eastern).strftime('%Y-%m-%d'))
        try:
            pub_datetime = datetime.strptime(date_str, '%Y-%m-%d')
            pub_datetime = eastern.localize(pub_datetime.replace(hour=12, minute=0, second=0))
        except ValueError:
            pub_datetime = datetime.now(eastern)
        
        # Build description with image, caption, and humor links
        description_parts = []
        
        # Caption
        if cartoon.get('caption'):
            description_parts.append(f'<p><em>{cartoon["caption"]}</em></p>')
        
        # Artist credit
        if cartoon.get('author'):
            description_parts.append(f'<p>Cartoon by {cartoon["author"]}</p>')
        
        # Source link to original
        cartoon_url = cartoon.get('url', '')
        if cartoon_url:
            description_parts.append(f'<p><a href="{cartoon_url}">View on The New Yorker</a></p>')
        
        # More Humor and Cartoons links
        humor_links = cartoon.get('humor_links', [])
        if humor_links:
            description_parts.append('<hr><p><strong>More Humor and Cartoons:</strong></p><ul>')
            for link in humor_links[:6]:
                description_parts.append(f'<li><a href="{link["url"]}">{link["title"]}</a></li>')
            description_parts.append('</ul>')
        
        description = '\n'.join(description_parts)
        
        entry = {
            'title': cartoon.get('title', f"Daily Cartoon - {date_str}"),
            'url': cartoon.get('url', comic_info['url']),
            'image_url': cartoon['image_url'],
            'pub_date': pub_datetime,
            'description': description,
            'id': cartoon.get('url', f"newyorker-{date_str}")
        }
        entries.append(entry)
    
    # Sort by date (newest first for display, but feed generator may re-sort)
    entries.sort(key=lambda x: x['pub_date'], reverse=True)
    
    # Keep only the most recent entries to avoid huge feeds
    entries = entries[:15]
    
    # Generate feed
    if entries:
        success = feed_gen.generate_feed(comic_info, entries)
        if success:
            logger.info(f"Generated feed with {len(entries)} entries")
        else:
            logger.error("Failed to generate feed")
    else:
        logger.warning("No entries to generate feed")


def main():
    """Main function to update New Yorker Daily Cartoon feed."""
    logger.info("=" * 80)
    logger.info("Updating New Yorker Daily Cartoon Feed")
    logger.info("=" * 80)
    
    # Load existing data to avoid re-scraping
    existing_data = load_existing_data()
    
    # Initialize scraper
    scraper = NewYorkerScraper()
    
    # Get list of recent cartoons
    logger.info("Fetching cartoon listing...")
    cartoon_list = scraper.get_cartoon_list(max_cartoons=15)
    
    if not cartoon_list:
        logger.error("Failed to get cartoon list")
        return 1
    
    logger.info(f"Found {len(cartoon_list)} cartoons on listing page")
    
    # Scrape individual cartoon pages (skip already-scraped)
    all_cartoons = []
    new_count = 0
    
    for cartoon in cartoon_list:
        url = cartoon['url']
        
        # Check if already scraped
        if url in existing_data:
            logger.info(f"  Using cached: {cartoon['title']}")
            all_cartoons.append(existing_data[url])
        else:
            logger.info(f"  Scraping: {cartoon['title']}")
            details = scraper.scrape_cartoon_page(url)
            if details:
                all_cartoons.append(details)
                new_count += 1
            else:
                logger.warning(f"  Failed to scrape: {cartoon['title']}")
    
    logger.info(f"Scraped {new_count} new cartoons, {len(all_cartoons) - new_count} from cache")
    
    if not all_cartoons:
        logger.error("No cartoons to process")
        return 1
    
    # Save scraped data
    if new_count > 0:
        save_data(all_cartoons)
    
    # Generate RSS feed
    logger.info("Generating RSS feed...")
    generate_feed(all_cartoons)
    
    logger.info("=" * 80)
    logger.info("New Yorker Daily Cartoon update complete!")
    logger.info("=" * 80)
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
