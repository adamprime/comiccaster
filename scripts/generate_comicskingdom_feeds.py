#!/usr/bin/env python3
"""
Generate RSS feeds for Comics Kingdom comics from scraped data.

Comics Kingdom serves its newest post for any date, so the scraper saves the
same strip again every night it stays up, each time under that night's address
(issue #207). A strip is therefore identified by its image set, and dated by
its first sighting: the earliest ``data/comicskingdom_YYYY-MM-DD.json`` that
holds it, read across all saved history.

- Each feed lists the strips first sighted in the 90 dates ending on the newest
  data file's date. The window is anchored on the data, not the clock.
- An item's guid, title and pub date come from the first-sighting record, so a
  later copy of the same strip never comes back under a new guid.
- A comic with nothing first sighted in the window is not written at all: its
  existing feed file stays byte-identical and no new one is created.

Because identity rests on all history, saved Comics Kingdom data must stay
append-only: no past-date scrapes, no relabeled records, no deleted files.
"""

import json
import logging
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
import pytz
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from comiccaster.comicskingdom_catalog import load_comicskingdom_catalog
from comiccaster.feed_generator import ComicFeedGenerator

logger = logging.getLogger(__name__)

# The window's first day is newest - (WINDOW_DAYS - 1), so a gap-free window
# holds exactly the 90 newest data files.
WINDOW_DAYS = 90

# Strict on purpose: a backup or misnamed file must not be read or anchor the window.
DATA_FILE_NAME = re.compile(r'^comicskingdom_(\d{4}-\d{2}-\d{2})\.json$')


def find_comicskingdom_data_files(data_dir) -> List[Tuple[date, Path]]:
    """Return every strictly named Comics Kingdom data file with its date, oldest first."""
    files = []
    for path in Path(data_dir).glob('comicskingdom_*.json'):
        match = DATA_FILE_NAME.match(path.name)
        if not match:
            continue
        try:
            files.append((date.fromisoformat(match.group(1)), path))
        except ValueError:
            logger.warning(f"Skipping {path}: its name is not a real date")
    files.sort()
    return files


def read_data_file(path: Path) -> list:
    """Return the records saved in one data file, or [] with a warning if unreadable."""
    try:
        with open(path, 'r') as f:
            records = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f"Skipping unreadable data file {path}: {e}")
        return []
    if not isinstance(records, list):
        logger.warning(f"Skipping data file {path}: expected a list of records, got {type(records).__name__}")
        return []
    return records


def image_urls(record: Dict) -> List[str]:
    """The record's strip images: ``image_urls`` for a multi-panel strip, else ``image_url``."""
    if 'image_urls' in record:
        return list(record['image_urls'])
    if 'image_url' in record:
        return [record['image_url']]
    return []


def check_record(record) -> None:
    """Raise ValueError unless the record has the fields an item is built from."""
    if not isinstance(record, dict):
        raise ValueError(f"not a record: {record!r:.80}")
    for field in ('slug', 'url', 'date'):
        if not isinstance(record.get(field), str):
            raise ValueError(f"{field} missing or not text")
    datetime.strptime(record['date'], '%Y-%m-%d')


def load_window_strips(files: List[Tuple[date, Path]]) -> Dict[str, List[Dict]]:
    """First-sighting records in the window, grouped by slug, oldest first.

    Every file is read, oldest first, and the first record holding a slug's image
    set is that strip's first sighting. Later copies of the set are ignored.
    """
    newest = files[-1][0]
    window_start = newest - timedelta(days=WINDOW_DAYS - 1)
    print(f"📂 Reading {len(files)} Comics Kingdom data file(s); "
          f"window {window_start} to {newest} (newest data file {files[-1][1].name})")

    first_sightings: Dict[Tuple[str, Tuple[str, ...]], Tuple[date, Dict]] = {}
    for file_date, path in files:
        for position, record in enumerate(read_data_file(path)):
            try:
                check_record(record)
            except ValueError as e:
                logger.warning(f"Skipping malformed record #{position} in {path}: {e}")
                continue
            images = image_urls(record)
            if not images:
                continue
            key = (record['slug'], tuple(sorted(images)))
            if key not in first_sightings:
                first_sightings[key] = (file_date, record)

    # Files are read oldest first, so first sightings are already in date order.
    grouped: Dict[str, List[Dict]] = {}
    for (slug, _), (file_date, record) in first_sightings.items():
        if file_date >= window_start:
            grouped.setdefault(slug, []).append(record)
    return grouped


def load_comics_list(catalog_dir='public') -> List[Dict]:
    """Load Comics Kingdom comics from the daily and political catalogs."""
    ck_comics = load_comicskingdom_catalog(catalog_dir)

    print(f"✅ Found {len(ck_comics)} Comics Kingdom comics in catalog (daily + political)")
    return ck_comics


def generate_feed_for_comic(comic_info: Dict, strips: List[Dict], generator: ComicFeedGenerator) -> bool:
    """Write one comic's feed from its first-sighted strips. Returns True when written.

    With no strip to list the feed is not written, so an existing file stays as it is.
    """
    entries = []
    for strip in strips:
        urls = image_urls(strip)
        if 'image_urls' in strip:
            images = [{'url': url, 'alt': f"{comic_info['name']} - Panel {i + 1}"}
                      for i, url in enumerate(urls)]
        else:
            images = [{'url': urls[0], 'alt': comic_info['name']}]
        entries.append({
            'title': f"{comic_info['name']} - {strip['date']}",
            'url': strip['url'],
            'images': images,
            'pub_date': datetime.strptime(strip['date'], '%Y-%m-%d').replace(tzinfo=pytz.UTC),
            'description': f"Comic strip for {strip['date']}",
            'id': strip['url'],
        })

    # Never replace a feed with an empty one.
    if not entries:
        return False

    try:
        if generator.generate_feed(comic_info, entries):
            print(f"  ✅ {comic_info['name']} ({len(entries)} strips)")
            return True
        print(f"  ❌ Failed: {comic_info['name']}")
        return False
    except Exception as e:
        print(f"  ❌ Error generating feed for {comic_info['name']}: {e}")
        return False


def main(data_dir='data', output_dir='public/feeds', catalog_dir='public'):
    """Generate every Comics Kingdom feed with a strip first sighted in the window."""
    print("="*80)
    print("Comics Kingdom Feed Generator")
    print("="*80)
    print()

    print("Step 1: Loading scraped Comics Kingdom data...")
    files = find_comicskingdom_data_files(data_dir)
    if not files:
        print(f"❌ No Comics Kingdom data files found in {data_dir}/. Run scraper first:")
        print("   python scripts/comicskingdom_scraper_individual.py")
        return 1
    strips_by_slug = load_window_strips(files)
    print()

    print("Step 2: Loading Comics Kingdom comics from catalog...")
    comics_list = load_comics_list(catalog_dir)
    if not comics_list:
        print("❌ No Comics Kingdom comics in catalog")
        return 1
    print()

    print("Step 3: Generating feeds...")
    generator = ComicFeedGenerator(
        base_url="https://comicskingdom.com",
        output_dir=str(output_dir)
    )

    written = 0
    untouched = 0

    for comic in comics_list:
        if generate_feed_for_comic(comic, strips_by_slug.get(comic['slug'], []), generator):
            written += 1
        else:
            untouched += 1

    print()
    print("="*80)
    print("✅ Feed Generation Complete!")
    print("="*80)
    print(f"Written: {written}")
    print(f"Untouched (no strip first sighted in the window): {untouched}")
    print(f"Total: {len(comics_list)}")
    print()
    print(f"Feeds saved to: {output_dir}/")
    print("="*80)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
