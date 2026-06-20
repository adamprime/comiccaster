#!/usr/bin/env python3
"""Scrape the Mr. Boffo daily strip into data/mrboffo_$DATE.json.

No feed generation — see scripts/generate_mrboffo_feeds.py for that. This
script only produces the authoritative pipeline input for the generator.

Mr. Boffo (by Joe Martin) is self-syndicated and runs on its own static site
at http://www.mrboffo.com/daily.html. The page only ever shows the current
strip — there is no per-day permalink or archive — so each run captures
"today's" strip and dates it by the Eastern fetch date, the same "daily dose"
model used by The Far Side.

Behavior note: writes today's file on every successful scrape. This matches the
convention used by the other scrapers and lets the push-recovery invariant
guard in local_master_update.sh be meaningful for Mr. Boffo. On failure it
writes nothing and exits non-zero, so the guard reports the miss.
"""

import json
import logging
import os
import sys
from datetime import datetime
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


def save_today(comics, data_dir=DATA_DIR):
    """Write today's Mr. Boffo snapshot.

    Output shape mirrors the Far Side daily snapshot:
        {"target_date": "YYYY-MM-DD", "scraped_at": "<iso8601 UTC>",
         "comics": [...]}
    """
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    target_date = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
    output = path / f'mrboffo_{target_date}.json'
    payload = {
        'target_date': target_date,
        'scraped_at': datetime.now(pytz.UTC).isoformat(),
        'comics': comics,
    }
    with open(output, 'w') as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Saved {len(comics)} comic(s) to {output}")
    return output


def main():
    logger.info("=" * 80)
    logger.info("Scraping Mr. Boffo daily strip")
    logger.info("=" * 80)

    scraper = ScraperFactory.get_scraper('mrboffo')
    result = scraper.scrape_comic()

    if not result or not result.get('images'):
        logger.error("No strip produced; not writing a snapshot")
        return 1

    # Persist a single per-day comic record carrying the image and title.
    comic = {
        'image_url': result['images'][0]['url'],
        'title': result.get('title', 'Mr. Boffo'),
        'url': result.get('url', scraper.DAILY_URL),
    }
    save_today([comic])
    logger.info("Done")
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
