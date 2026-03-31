#!/usr/bin/env python3
"""
Backfill GoComics feeds by fetching individual comic pages.

This script is for manual recovery when feeds are missing entries.
It is NOT part of the daily automated pipeline.

Usage:
    python scripts/backfill_gocomics_feeds.py --comic garfield --days 5
    python scripts/backfill_gocomics_feeds.py --all --days 10
"""

import argparse
import json
import logging
import sys
import time
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.update_feeds import (
    scrape_comic_enhanced_http,
    regenerate_feed,
    load_comics_list,
    load_political_comics_list,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone('US/Eastern')
MAX_WORKERS = 2
BATCH_DELAY = 1.5


def backfill_comic(comic_info: Dict, days: int) -> bool:
    """Backfill a single comic's feed by fetching individual pages.

    Returns True if at least one new entry was added.
    """
    today = datetime.now(TIMEZONE)
    target_dates = [
        (today - timedelta(days=i)).strftime('%Y/%m/%d')
        for i in range(days - 1, -1, -1)
    ]

    scraped_entries = []

    # Scrape dates with limited concurrency and delays between batches
    for i in range(0, len(target_dates), MAX_WORKERS):
        batch = target_dates[i:i + MAX_WORKERS]

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_date = {
                executor.submit(scrape_comic_enhanced_http, comic_info['slug'], date_str): date_str
                for date_str in batch
            }

            for future in concurrent.futures.as_completed(future_to_date):
                date_str = future_to_date[future]
                try:
                    metadata = future.result()
                    if metadata:
                        try:
                            pub_date = datetime.strptime(date_str, '%Y/%m/%d').replace(tzinfo=pytz.UTC)
                        except ValueError:
                            continue
                        metadata['pub_date'] = pub_date
                        scraped_entries.append(metadata)
                        logger.info(f"  Scraped {comic_info['name']} for {date_str}")
                    else:
                        logger.debug(f"  No data for {comic_info['name']} on {date_str}")
                except Exception as e:
                    logger.error(f"  Error scraping {comic_info['name']} on {date_str}: {e}")

        # Rate limit between batches
        if i + MAX_WORKERS < len(target_dates):
            time.sleep(BATCH_DELAY)

    if not scraped_entries:
        logger.warning(f"No entries scraped for {comic_info['name']}")
        return False

    scraped_entries.sort(key=lambda x: x['pub_date'], reverse=True)

    logger.info(f"Regenerating feed for {comic_info['name']} with {len(scraped_entries)} entries")
    return bool(regenerate_feed(comic_info, scraped_entries))


def get_comic_by_slug(slug: str) -> Optional[Dict]:
    """Find a comic in the catalog by slug."""
    for comic in load_comics_list():
        if comic['slug'] == slug:
            return comic
    for comic in load_political_comics_list():
        if comic['slug'] == slug:
            return comic
    return None


def main():
    parser = argparse.ArgumentParser(description='Backfill GoComics feeds')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--comic', type=str, help='Comic slug to backfill')
    group.add_argument('--all', action='store_true', help='Backfill all comics')
    parser.add_argument('--days', type=int, default=10, help='Number of days to backfill (default: 10)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("GoComics Feed Backfill")
    logger.info(f"Days to backfill: {args.days}")
    logger.info("=" * 60)

    if args.comic:
        comic = get_comic_by_slug(args.comic)
        if not comic:
            logger.error(f"Comic '{args.comic}' not found in catalog")
            return 1
        comics_to_process = [comic]
    else:
        comics_to_process = load_comics_list() + load_political_comics_list()

    logger.info(f"Processing {len(comics_to_process)} comics")

    updated = 0
    skipped = 0
    failed = 0

    for i, comic in enumerate(comics_to_process, 1):
        logger.info(f"[{i}/{len(comics_to_process)}] {comic['name']}")
        try:
            if backfill_comic(comic, args.days):
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            logger.error(f"Failed to backfill {comic['name']}: {e}")
            failed += 1

        # Rate limit between comics when processing all
        if args.all and i < len(comics_to_process):
            time.sleep(BATCH_DELAY)

    logger.info("=" * 60)
    logger.info("Backfill Complete")
    logger.info(f"  Updated: {updated}")
    logger.info(f"  Skipped (no data): {skipped}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Total: {len(comics_to_process)}")
    logger.info("=" * 60)

    return 1 if failed > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
