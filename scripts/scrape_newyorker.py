#!/usr/bin/env python3
"""Scrape The New Yorker Daily Cartoon listing into data/newyorker_$DATE.json.

No feed generation — see scripts/generate_newyorker_feeds.py for that. This
script only produces the authoritative pipeline input for the generator.

Behavior note: writes today's file on every successful scrape, even if every
cartoon in the listing was already cached from a previous day. This matches
the convention used by the GoComics, Comics Kingdom, and TinyView scrapers
and lets the push-recovery invariant guard in local_master_update.sh be
meaningful for New Yorker.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.newyorker_scraper import NewYorkerScraper  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def load_cache(data_dir='data'):
    """Build a URL -> cartoon dict from all newyorker_*.json files.

    Used to skip re-scraping individual cartoon pages we've already fetched.
    Errors loading any one file are logged and skipped; the cache is
    best-effort.
    """
    cache = {}
    for json_file in sorted(Path(data_dir).glob('newyorker_*.json')):
        try:
            with open(json_file) as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Error loading {json_file}: {e}")
            continue
        for cartoon in data.get('cartoons', []):
            url = cartoon.get('url')
            if url:
                cache[url] = cartoon
    logger.info(f"Loaded {len(cache)} cartoons into cache from existing data")
    return cache


def save_today(cartoons, data_dir='data'):
    """Write today's New Yorker snapshot.

    Output shape matches what update_newyorker_feeds.py historically produced:
        {"scraped_at": "<iso8601 UTC>", "cartoons": [...]}
    """
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
    output = path / f'newyorker_{date_str}.json'
    payload = {
        'scraped_at': datetime.now(pytz.UTC).isoformat(),
        'cartoons': cartoons,
    }
    with open(output, 'w') as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Saved {len(cartoons)} cartoons to {output}")
    return output


def main():
    logger.info("=" * 80)
    logger.info("Scraping New Yorker Daily Cartoon")
    logger.info("=" * 80)

    cache = load_cache()
    scraper = NewYorkerScraper()

    listing = scraper.get_cartoon_list(max_cartoons=15)
    if not listing:
        logger.error("Failed to get cartoon listing")
        return 1
    logger.info(f"Listing has {len(listing)} cartoons")

    cartoons = []
    new_count = 0
    for item in listing:
        url = item['url']
        if url in cache:
            logger.info(f"  cached:   {item['title']}")
            cartoons.append(cache[url])
        else:
            logger.info(f"  scraping: {item['title']}")
            detail = scraper.scrape_cartoon_page(url)
            if detail:
                cartoons.append(detail)
                new_count += 1
            else:
                logger.warning(f"  failed:   {item['title']}")

    if not cartoons:
        logger.error("No cartoons produced; not writing a snapshot")
        return 1

    save_today(cartoons)
    logger.info(f"Done: {new_count} newly scraped, {len(cartoons) - new_count} from cache")
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
