#!/usr/bin/env python3
"""Generate the New Yorker Daily Cartoon RSS feed from scraped data.

Reads the most recent data/newyorker_*.json snapshot (produced by
scripts/scrape_newyorker.py) and writes public/feeds/newyorker-daily-cartoon.xml.

Network-free: no scraping happens here. Safe to run during push-recovery
after a reset when we want to rebuild feeds from authoritative scrape data.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.feed_generator import ComicFeedGenerator  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

COMIC_INFO = {
    'name': 'Daily Cartoon',
    'slug': 'newyorker-daily-cartoon',
    'author': 'The New Yorker',
    'url': 'https://www.newyorker.com/cartoons/daily-cartoon',
    'source': 'newyorker',
}
MAX_ENTRIES = 15


def find_latest_data(data_dir='data'):
    """Return the most recent newyorker_*.json path, or None."""
    files = sorted(Path(data_dir).glob('newyorker_*.json'))
    return files[-1] if files else None


def load_cartoons(path):
    with open(path) as f:
        data = json.load(f)
    return data.get('cartoons', [])


def build_entry(cartoon):
    """Build a single feed entry from a cartoon record.

    Returns None for cartoons missing required fields (currently: image_url).
    Output shape and formatting match what update_newyorker_feeds.py produced
    so the generated feed stays byte-stable across the refactor.
    """
    if not cartoon.get('image_url'):
        return None

    eastern = pytz.timezone('US/Eastern')
    date_str = cartoon.get('date', datetime.now(eastern).strftime('%Y-%m-%d'))
    try:
        pub_datetime = datetime.strptime(date_str, '%Y-%m-%d')
        pub_datetime = eastern.localize(pub_datetime.replace(hour=12, minute=0, second=0))
    except ValueError:
        pub_datetime = datetime.now(eastern)

    parts = []
    if cartoon.get('caption'):
        parts.append(f'<p><em>{cartoon["caption"]}</em></p>')
    if cartoon.get('author'):
        parts.append(f'<p>Cartoon by {cartoon["author"]}</p>')
    cartoon_url = cartoon.get('url', '')
    if cartoon_url:
        parts.append(f'<p><a href="{cartoon_url}">View on The New Yorker</a></p>')
    humor_links = cartoon.get('humor_links') or []
    if humor_links:
        parts.append('<hr><p><strong>More Humor and Cartoons:</strong></p><ul>')
        for link in humor_links[:6]:
            parts.append(f'<li><a href="{link["url"]}">{link["title"]}</a></li>')
        parts.append('</ul>')
    description = '\n'.join(parts)

    return {
        'title': cartoon.get('title', f"Daily Cartoon - {date_str}"),
        'url': cartoon.get('url', COMIC_INFO['url']),
        'image_url': cartoon['image_url'],
        'pub_date': pub_datetime,
        'description': description,
        'id': cartoon.get('url', f"newyorker-{date_str}"),
    }


def main():
    logger.info("=" * 80)
    logger.info("Generating New Yorker Daily Cartoon feed")
    logger.info("=" * 80)

    latest = find_latest_data()
    if not latest:
        logger.warning("No newyorker_*.json files found; nothing to generate")
        return 0
    logger.info(f"Reading data from {latest}")

    cartoons = load_cartoons(latest)
    entries = [e for e in (build_entry(c) for c in cartoons) if e is not None]
    entries.sort(key=lambda x: x['pub_date'], reverse=True)
    entries = entries[:MAX_ENTRIES]

    if not entries:
        logger.warning("No usable entries in latest data file; skipping")
        return 0

    feed_gen = ComicFeedGenerator(
        base_url="https://www.newyorker.com",
        output_dir='public/feeds',
    )
    if feed_gen.generate_feed(COMIC_INFO, entries):
        logger.info(f"Generated feed with {len(entries)} entries")
        return 0
    logger.error("Failed to generate feed")
    return 1


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
