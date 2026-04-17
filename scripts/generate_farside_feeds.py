#!/usr/bin/env python3
"""Generate The Far Side RSS feeds from scraped data.

Reads data/farside_daily_*.json (per target date) and
data/farside_new_*.json (per scrape date), writes
public/feeds/farside-daily.xml and public/feeds/farside-new.xml.

Network-free: no scraping here. Safe to call during push-recovery after
reset to origin/main.

Feed construction preserves the conventions of the original combined
update_farside_feeds.py:

- Daily Dose: 15 entries across the 3 most recent target dates (5 per
  day), ordered oldest-first during iteration so that pub_time minutes
  increase monotonically (day1 08:00-08:04, day2 08:05-08:09,
  day3 08:10-08:14). Title is "The Far Side - YYYY-MM-DD #N" where N
  cycles 1..5 within each day.

- New Stuff: entries for every newly-detailed comic in the latest
  snapshot, with pub_times stepped 1 day apart starting at scraped_at
  (to sidestep feed-generator date-based dedup).
"""

import glob
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.feed_generator import ComicFeedGenerator  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

DATA_DIR = Path('data')
OUTPUT_DIR = 'public/feeds'
DAILY_WINDOW = 3  # Number of target-date files to include in the daily feed.

DAILY_COMIC_INFO = {
    'name': 'The Far Side - Daily Dose',
    'slug': 'farside-daily',
    'author': 'Gary Larson',
    'url': 'https://www.thefarside.com/',
    'source': 'farside-daily',
}
NEW_COMIC_INFO = {
    'name': 'The Far Side - New Stuff',
    'slug': 'farside-new',
    'author': 'Gary Larson',
    'url': 'https://www.thefarside.com/new-stuff',
    'source': 'farside-new',
}


# -- Daily Dose -------------------------------------------------------------

def find_daily_snapshots(data_dir=DATA_DIR):
    """Return the DAILY_WINDOW most recent farside_daily_*.json paths,
    sorted oldest target_date first (matches scrape iteration order)."""
    pattern = str(Path(data_dir) / 'farside_daily_*.json')
    paths = sorted(glob.glob(pattern))  # lexicographic == date order
    # Take the last (most recent) DAILY_WINDOW, then keep them oldest-first.
    return paths[-DAILY_WINDOW:]


def load_daily_snapshot(path):
    with open(path) as f:
        data = json.load(f)
    target_date_str = data.get('target_date')
    comics = data.get('comics', [])
    return target_date_str, comics


def build_daily_entries(snapshots):
    """Build feed entries from an ordered list of (target_date, comics).

    `snapshots` is in oldest-first target_date order. Global index `i`
    drives both pub_time minutes and the title #N (mod 5). Comics with
    no image_url are skipped (same as original).
    """
    eastern = pytz.timezone('US/Eastern')
    entries = []
    i = 0
    for target_date_str, comics in snapshots:
        try:
            target_date = eastern.localize(datetime.strptime(target_date_str, '%Y-%m-%d'))
        except Exception as e:
            logger.warning(f"Skipping snapshot with bad target_date '{target_date_str}': {e}")
            continue
        for comic in comics:
            image_url = comic.get('image_url')
            if not image_url:
                i += 1
                continue
            caption = comic.get('caption', '')
            description = (
                f'<div style="text-align: center; max-width: 700px; margin: 0 auto;">'
                f'<img src="{image_url}" alt="The Far Side comic" style="max-width: 100%; height: auto;"/>'
                f'</div>'
            )
            if caption:
                description += f'<p style="margin-top: 10px; font-style: italic;">{caption}</p>'
            description += (
                '<p style="margin-top: 15px; font-size: 0.9em;">'
                '<a href="https://www.thefarside.com/">Visit The Far Side</a> | © Gary Larson'
                '</p>'
            )
            pub_time = target_date.replace(hour=8, minute=i, second=0, microsecond=0)
            date_formatted = pub_time.strftime('%Y-%m-%d')
            entries.append({
                'title': f"The Far Side - {date_formatted} #{(i % 5) + 1}",
                'url': comic.get('url', DAILY_COMIC_INFO['url']),
                'description': description,
                'pub_date': pub_time.strftime('%a, %d %b %Y %H:%M:%S %z'),
            })
            i += 1
    return entries


def generate_daily_feed():
    paths = find_daily_snapshots()
    if not paths:
        logger.warning("No farside_daily_*.json snapshots; skipping daily feed")
        return True
    logger.info(f"Daily Dose: using {len(paths)} snapshot(s): {', '.join(Path(p).name for p in paths)}")
    snapshots = [load_daily_snapshot(p) for p in paths]
    entries = build_daily_entries(snapshots)
    if not entries:
        logger.warning("No entries produced for Daily Dose feed")
        return True
    feed_gen = ComicFeedGenerator(output_dir=OUTPUT_DIR)
    if feed_gen.generate_feed(DAILY_COMIC_INFO, entries):
        logger.info(f"Generated Daily Dose feed with {len(entries)} entries")
        return True
    logger.error("Failed to generate Daily Dose feed")
    return False


# -- New Stuff --------------------------------------------------------------

_NEW_DATE_RE = re.compile(r'farside_new_(\d{4}-\d{2}-\d{2})\.json$')


def find_latest_new_snapshot(data_dir=DATA_DIR):
    """Return path of most recent farside_new_YYYY-MM-DD.json, or None.

    Intentionally matches only the dated-snapshot naming from this refactor;
    a stray non-matching file cannot confuse the selection.
    """
    candidates = []
    for p in Path(data_dir).glob('farside_new_*.json'):
        m = _NEW_DATE_RE.search(p.name)
        if m:
            candidates.append((m.group(1), p))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def build_new_stuff_entries(scraped_at, comics):
    """Given a scraped_at datetime and list of detailed comics, build entries.

    Pub times step 1 day apart starting from scraped_at (to avoid feed-gen
    date dedup). Caption may be empty; image_url is required.
    """
    entries = []
    for i, comic in enumerate(comics):
        image_url = comic.get('image_url')
        if not image_url:
            continue
        title = comic.get('title') or ''
        caption = comic.get('caption') or ''
        description = (
            f'<div style="text-align: center; max-width: 700px; margin: 0 auto;">'
            f'<img src="{image_url}" alt="{title}" style="max-width: 100%; height: auto;"/>'
            f'</div>'
        )
        if caption:
            description += f'<p style="margin-top: 10px;">{caption}</p>'
        description += (
            '<p style="margin-top: 15px; font-size: 0.9em;">'
            '<a href="https://www.thefarside.com/new-stuff">See all new work</a> | © Gary Larson'
            '</p>'
        )
        pub_time = scraped_at - timedelta(days=i)
        entries.append({
            'title': f"The Far Side - New Stuff: {title}",
            'url': comic.get('url', NEW_COMIC_INFO['url']),
            'description': description,
            'pub_date': pub_time.strftime('%a, %d %b %Y %H:%M:%S %z'),
        })
    return entries


def generate_new_stuff_feed():
    latest = find_latest_new_snapshot()
    if not latest:
        logger.warning("No farside_new_*.json snapshot; skipping new stuff feed")
        return True
    logger.info(f"New Stuff: using {latest}")
    with open(latest) as f:
        data = json.load(f)
    comics = data.get('comics', [])
    scraped_at_raw = data.get('scraped_at')
    try:
        scraped_at = datetime.fromisoformat(scraped_at_raw)
    except Exception as e:
        logger.warning(f"Bad scraped_at '{scraped_at_raw}': {e}; using now()")
        scraped_at = datetime.now(pytz.timezone('US/Eastern'))
    entries = build_new_stuff_entries(scraped_at, comics)
    feed_gen = ComicFeedGenerator(output_dir=OUTPUT_DIR)
    if feed_gen.generate_feed(NEW_COMIC_INFO, entries):
        logger.info(f"Generated New Stuff feed with {len(entries)} entries")
        return True
    logger.error("Failed to generate New Stuff feed")
    return False


# -- Entry point ------------------------------------------------------------

def main():
    logger.info("Generating Far Side feeds")
    daily_ok = generate_daily_feed()
    new_ok = generate_new_stuff_feed()
    logger.info("=" * 80)
    if daily_ok and new_ok:
        logger.info("Far Side feed generation complete")
        return 0
    logger.error("Far Side feed generation completed with errors")
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
