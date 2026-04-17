#!/usr/bin/env python3
"""Scrape The Far Side into data files. No feed generation.

Writes two kinds of snapshots:

- data/farside_daily_YYYY-MM-DD.json: one file per target date, containing
  the 5 comics the Far Side site showed as that day's "Daily Dose". The
  site serves today + 2 days back, so this script scrapes 3 target dates
  per run. Older files are left alone — the generator selects the most
  recent 3 by target_date.

- data/farside_new_YYYY-MM-DD.json: one file per scrape date, containing
  any newly-detailed "New Stuff" comics (past data/farside_new_last_id.txt).
  Preserves the per-run cursor semantics of the original script.

Side effects: data/farside_new_last_id.txt is updated to the archive's
current max id. See scripts/generate_farside_feeds.py for feed rendering.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.scraper_factory import ScraperFactory  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

DATA_DIR = Path('data')
LAST_ID_FILE = DATA_DIR / 'farside_new_last_id.txt'
# Initial-population seed count when last_id is unset or feed is missing.
# Preserved from the original script's behavior.
INITIAL_NEW_STUFF_SEED = 10


def save_daily_snapshot(target_date_str, comics):
    """Write data/farside_daily_<date>.json.

    Overwrites any existing file for that target_date. Content layout is
    deliberately stable so the generator can consume it without needing to
    know how it was produced.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f'farside_daily_{target_date_str}.json'
    payload = {
        'target_date': target_date_str,
        'scraped_at': datetime.now(pytz.UTC).isoformat(),
        'comics': comics,
    }
    with open(out, 'w') as f:
        json.dump(payload, f, indent=2)
    logger.info(f"  wrote {out} ({len(comics)} comics)")
    return out


def scrape_daily():
    """Scrape the 3-day Daily Dose window into per-date JSON files."""
    logger.info("=" * 80)
    logger.info("Scraping Far Side Daily Dose (last 3 days)")
    logger.info("=" * 80)

    scraper = ScraperFactory.get_scraper('farside-daily')
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)

    any_success = False
    for days_ago in range(2, -1, -1):
        target = now_eastern - timedelta(days=days_ago)
        date_slash = target.strftime('%Y/%m/%d')
        date_dash = target.strftime('%Y-%m-%d')
        logger.info(f"Scraping target date {date_dash}...")
        result = scraper.scrape_daily_dose(date_slash)
        if not result or 'comics' not in result:
            logger.warning(f"  scrape returned no comics for {date_dash}")
            continue
        comics = result['comics']
        logger.info(f"  scraped {len(comics)} comics")
        save_daily_snapshot(date_dash, comics)
        any_success = True
    return any_success


def load_cursor():
    """Read last known New Stuff comic id. Returns 0 if unset/unreadable."""
    if not LAST_ID_FILE.exists():
        return 0
    try:
        return int(LAST_ID_FILE.read_text().strip())
    except Exception as e:
        logger.warning(f"Could not read {LAST_ID_FILE}: {e}; treating as 0")
        return 0


def write_cursor(max_id):
    LAST_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_ID_FILE.write_text(str(max_id))


def save_new_stuff_snapshot(scraped_at, cursor_before, cursor_after, is_initial, comics):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    eastern_date = scraped_at.astimezone(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
    out = DATA_DIR / f'farside_new_{eastern_date}.json'
    payload = {
        'scraped_at': scraped_at.isoformat(),
        'cursor_before': cursor_before,
        'cursor_after': cursor_after,
        'is_initial': is_initial,
        'comics': comics,
    }
    with open(out, 'w') as f:
        json.dump(payload, f, indent=2)
    logger.info(f"  wrote {out} ({len(comics)} newly-detailed comics)")
    return out


def scrape_new_stuff():
    """Scrape the New Stuff archive, detail only new comics, write snapshot."""
    logger.info("=" * 80)
    logger.info("Scraping Far Side New Stuff")
    logger.info("=" * 80)

    scraper = ScraperFactory.get_scraper('farside-new')
    eastern = pytz.timezone('US/Eastern')
    scraped_at = datetime.now(eastern)

    cursor_before = load_cursor()
    logger.info(f"Cursor before scrape: {cursor_before}")

    result = scraper.scrape_new_stuff()
    if not result or 'comics' not in result:
        logger.error("scrape_new_stuff returned no data")
        return False

    archive = result['comics']
    logger.info(f"Archive has {len(archive)} comics")

    # Decide which comics to detail: initial seed, or strictly new past cursor.
    feed_path = Path('public/feeds/farside-new.xml')
    is_initial = (cursor_before == 0) or (not feed_path.exists())
    if is_initial:
        logger.info(f"Initial population: seeding with {INITIAL_NEW_STUFF_SEED} most recent")
        to_detail = sorted(archive, key=lambda c: int(c['id']), reverse=True)[:INITIAL_NEW_STUFF_SEED]
    else:
        to_detail = [c for c in archive if int(c['id']) > cursor_before]
        logger.info(f"Found {len(to_detail)} new comics since cursor {cursor_before}")

    detailed = []
    for comic in to_detail:
        logger.info(f"  detailing comic {comic['id']}...")
        detail = scraper.scrape_new_stuff_detail(comic['url'])
        if detail:
            detailed.append(detail)
        else:
            logger.warning(f"  failed to detail {comic['id']}")

    cursor_after = cursor_before
    if archive:
        cursor_after = max(int(c['id']) for c in archive)
        if cursor_after != cursor_before:
            write_cursor(cursor_after)
            logger.info(f"Cursor advanced: {cursor_before} -> {cursor_after}")
        else:
            logger.info("Cursor unchanged")

    save_new_stuff_snapshot(
        scraped_at=scraped_at,
        cursor_before=cursor_before,
        cursor_after=cursor_after,
        is_initial=is_initial,
        comics=detailed,
    )
    return True


def main():
    logger.info("Starting Far Side scrape")

    daily_ok = scrape_daily()
    new_ok = scrape_new_stuff()

    logger.info("=" * 80)
    if daily_ok and new_ok:
        logger.info("Far Side scrape complete")
        return 0
    logger.error("Far Side scrape completed with errors")
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
