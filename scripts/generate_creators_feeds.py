#!/usr/bin/env python3
"""Generate RSS feeds for Creators Syndicate comics from scraped data.

Reads the most recent data/creators_*.json snapshot (produced by
scripts/scrape_creators.py) and the live public/comics_list.json catalog,
joining by slug. Writes one feed per Creators comic to public/feeds/.

Network-free: no scraping happens here. Safe to call during push-recovery
after reset to origin/main.
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

CATALOG_PATH = Path("public/comics_list.json")
DATA_DIR = Path("data")
OUTPUT_DIR = "public/feeds"
MAX_ENTRIES_PER_FEED = 30

_SNAPSHOT_DATE_RE = re.compile(r'^creators_(\d{4}-\d{2}-\d{2})\.json$')


def find_latest_snapshot(data_dir=DATA_DIR):
    """Return the most recent data/creators_YYYY-MM-DD.json path, or None.

    Filters out non-date-shaped files (e.g., the pre-existing
    creators_discovery_report.json) so the selection is unambiguous.
    """
    candidates = []
    for p in Path(data_dir).glob('creators_*.json'):
        m = _SNAPSHOT_DATE_RE.match(p.name)
        if m:
            candidates.append((m.group(1), p))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def load_catalog():
    """Return list of Creators comic_info dicts from the live catalog."""
    with open(CATALOG_PATH, encoding="utf-8") as f:
        all_comics = json.load(f)
    creators = [c for c in all_comics if c.get("source") == "creators"]
    return creators


def build_entries_for_comic(comic_info, releases):
    """Given comic_info and the scraped raw releases list, return feed entries.

    Output shape and ordering match what the pre-refactor combined script
    produced: entries sorted ascending by pub_date (UTC from release_date),
    title falls back to "{comic name} - {release_date}" when the release has
    no title, description is a short date stub, images has a single entry
    with the `full` URL falling back to `thumb` — all preserved for feed-XML
    stability across the refactor.
    """
    entries = []
    for release in releases[:MAX_ENTRIES_PER_FEED]:
        release_date = release.get("release_date")
        image_url = release.get("full") or release.get("thumb")
        entry_url = release.get("formatted_url")
        if not release_date or not image_url or not entry_url:
            continue
        try:
            pub_date = datetime.strptime(release_date, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
        entries.append({
            "title": release.get("title") or f"{comic_info['name']} - {release_date}",
            "url": entry_url,
            "images": [{"url": image_url, "alt": comic_info.get("name", "Comic")}],
            "pub_date": pub_date,
            "description": f"Comic strip for {release_date}",
            "id": entry_url,
        })
    entries.sort(key=lambda x: x["pub_date"])
    return entries


def main():
    print("=" * 80)
    print("Creators Feed Generator")
    print("=" * 80)

    snapshot_path = find_latest_snapshot()
    if not snapshot_path:
        logger.warning("No data/creators_*.json snapshot found; nothing to generate")
        return 0
    logger.info(f"Reading data from {snapshot_path}")
    with open(snapshot_path) as f:
        snapshot = json.load(f)

    catalog = load_catalog()
    catalog_by_slug = {c["slug"]: c for c in catalog}
    logger.info(f"✅ Found {len(catalog)} Creators comics in catalog")

    generator = ComicFeedGenerator(base_url="https://www.creators.com", output_dir=OUTPUT_DIR)

    successful = 0
    failed = 0
    for comic_data in snapshot.get("comics", []):
        slug = comic_data.get("slug")
        comic_info = catalog_by_slug.get(slug)
        if not comic_info:
            logger.warning(f"  ⚠️  Scraped comic {slug} no longer in catalog; skipping")
            failed += 1
            continue
        entries = build_entries_for_comic(comic_info, comic_data.get("releases", []))
        if not entries:
            print(f"  ⚠️  No entries for {comic_info['name']}")
            failed += 1
            continue
        if generator.generate_feed(comic_info, entries):
            print(f"  ✅ {comic_info['name']} ({len(entries)} entries)")
            successful += 1
        else:
            print(f"  ❌ Failed: {comic_info['name']}")
            failed += 1

    print()
    print("=" * 80)
    print("✅ Feed Generation Complete!")
    print("=" * 80)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(snapshot.get('comics', []))}")
    print("Feeds saved to: public/feeds/")
    return 0 if successful > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
