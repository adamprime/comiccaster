#!/usr/bin/env python3
"""Generate the Mr. Boffo RSS feed from scraped data.

Reads the most recent data/mrboffo_*.json snapshots (produced by
scripts/scrape_mrboffo.py) and writes public/feeds/mr-boffo.xml.

Network-free: no scraping happens here. Safe to run during push-recovery
after a reset when we want to rebuild feeds from authoritative scrape data.

The Mr. Boffo page shows one strip per day with no per-day permalink or date
metadata, so each captured snapshot holds a single strip dated by its Eastern
fetch date. We keep a small rolling window of recent strips in the feed and
date each at noon Eastern on its capture day; because the days differ, the
pub_dates are naturally distinct and never collide in feed dedup.
"""

import json
import logging
import os
import re
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
    'name': 'Mr. Boffo',
    'slug': 'mr-boffo',
    'author': 'Joe Martin',
    'url': 'http://www.mrboffo.com/',
    'source': 'mrboffo',
}

DATA_DIR = Path('data')
OUTPUT_DIR = 'public/feeds'
# How many recent days of strips to keep in the feed.
FEED_WINDOW = 7

# Only consider date-shaped snapshot files (mrboffo_YYYY-MM-DD.json), so stray
# files like mrboffo_notes.json never win the "latest" selection.
_DATE_RE = re.compile(r'mrboffo_(\d{4}-\d{2}-\d{2})\.json$')


def find_snapshots(data_dir=DATA_DIR, window=FEED_WINDOW):
    """Return up to ``window`` most recent date-shaped snapshot paths.

    Oldest-first, so feed entries build in ascending pub_date order.
    """
    dated = []
    for path in Path(data_dir).glob('mrboffo_*.json'):
        if _DATE_RE.search(path.name):
            dated.append(path)
    dated.sort(key=lambda p: p.name)  # lexicographic == chronological
    return dated[-window:]


def find_latest_snapshot(data_dir=DATA_DIR):
    """Return the single most recent date-shaped snapshot path, or None."""
    snapshots = find_snapshots(data_dir, window=1)
    return snapshots[-1] if snapshots else None


def load_snapshot(path):
    """Return (target_date_str, comics) for a snapshot file."""
    with open(path) as f:
        data = json.load(f)
    target_date = data.get('target_date')
    if not target_date:
        # Fall back to the date embedded in the filename.
        match = _DATE_RE.search(Path(path).name)
        target_date = match.group(1) if match else ''
    return target_date, data.get('comics', [])


def build_entries(snapshots):
    """Build feed entries from a list of (target_date_str, comics) tuples.

    Each snapshot contributes its single strip. Strips missing an image_url are
    skipped. Entries are returned oldest-first.
    """
    eastern = pytz.timezone('US/Eastern')
    entries = []

    for target_date, comics in snapshots:
        for comic in comics:
            image_url = comic.get('image_url')
            if not image_url:
                continue

            try:
                pub_datetime = datetime.strptime(target_date, '%Y-%m-%d')
                pub_datetime = eastern.localize(
                    pub_datetime.replace(hour=12, minute=0, second=0)
                )
            except ValueError:
                pub_datetime = datetime.now(eastern)

            entries.append({
                'title': f"Mr. Boffo - {target_date}",
                'url': comic.get('url', COMIC_INFO['url']),
                'image_url': image_url,
                'images': [{'url': image_url, 'alt': 'Mr. Boffo'}],
                'pub_date': pub_datetime,
                'description': f'<p>Mr. Boffo by Joe Martin — {target_date}</p>',
                'id': f"mrboffo-{target_date}",
            })

    return entries


def main():
    logger.info("=" * 80)
    logger.info("Generating Mr. Boffo feed")
    logger.info("=" * 80)

    snapshot_paths = find_snapshots()
    if not snapshot_paths:
        logger.warning("No mrboffo_*.json files found; nothing to generate")
        return 0
    logger.info(f"Reading {len(snapshot_paths)} snapshot(s)")

    snapshots = [load_snapshot(p) for p in snapshot_paths]
    entries = build_entries(snapshots)

    if not entries:
        logger.warning("No usable entries in snapshots; skipping")
        return 0

    feed_gen = ComicFeedGenerator(
        base_url=COMIC_INFO['url'],
        output_dir=OUTPUT_DIR,
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
