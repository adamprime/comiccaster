#!/usr/bin/env python3
"""
Generate TinyView RSS feeds from pre-scraped JSON data.

Each feed carries every usable strip saved with a strip date in the 90 days up
to the newest ``data/tinyview_YYYY-MM-DD.json`` (the boundary day counts as
inside). The window is anchored on the data rather than the clock, so rebuilding
from the same files gives the same feeds on any host and in pipeline recovery.

- Strips are identified by their canonical address. Data files are read oldest
  to newest and the earliest-recorded usable copy of a strip wins, so a
  published item never swaps its content for a later copy.
- Each strip keeps only the images under its own strip folder on the TinyView
  CDN; a record carrying a same-date sibling's panels loses them.
- A comic with no usable strip in the window is not written at all: its existing
  feed file stays byte-identical and no new one is created.

Item fields are derived as they were when this script read only the newest data
file: the guid is the strip address, the title is the record's ``name``, and the
pub date is the strip date at 23:59:59 UTC.
"""

import sys
import os
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.feed_generator import ComicFeedGenerator
from comiccaster.tinyview_strips import canonical_strip_url, image_belongs_to_strip

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WINDOW_DAYS = 90

# Strict on purpose: data/tinyview_2025-11-16_backup.json must not be read.
DATA_FILE_NAME = re.compile(r'^tinyview_(\d{4}-\d{2}-\d{2})\.json$')


def parse_strip_date(value) -> date:
    """Parse a saved strip date: ``YYYY-MM-DD``, or the legacy ``YYYY/MM/DD``."""
    return datetime.strptime(str(value).replace('/', '-'), '%Y-%m-%d').date()


def find_tinyview_data_files(data_dir) -> List[Tuple[date, Path]]:
    """Return every strictly named TinyView data file with its date, oldest first."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        logger.error(f"Data directory not found: {data_dir}")
        return []

    files = []
    for path in data_dir.glob('tinyview_*.json'):
        match = DATA_FILE_NAME.match(path.name)
        if not match:
            continue
        try:
            files.append((parse_strip_date(match.group(1)), path))
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
        logger.warning(f"Skipping data file {path}: expected a list of strips, got {type(records).__name__}")
        return []
    return records


def own_strip(record) -> Tuple[date, str, dict]:
    """Return (strip date, canonical address, record with only its own images).

    Raises ValueError, KeyError or TypeError for a record that is not a strip.
    A record with no images of its own comes back with an empty ``images`` list.
    """
    if not isinstance(record, dict):
        raise ValueError(f"not a strip record: {record!r:.80}")
    slug, url = record['slug'], record['url']
    if not isinstance(slug, str) or not isinstance(url, str):
        raise ValueError(f"slug and url must be text: {slug!r}, {url!r}")
    strip_date = parse_strip_date(record['date'])

    images = record.get('images') or []
    if not isinstance(images, list):
        raise ValueError(f"images must be a list, got {type(images).__name__}")
    images = [
        image for image in images
        if isinstance(image, dict)
        and isinstance(image.get('url'), str)
        and image_belongs_to_strip(image['url'], url)
    ]
    return strip_date, canonical_strip_url(url), {**record, 'images': images}


def load_window_strips(data_dir) -> Dict[str, List[dict]]:
    """Load every usable strip in the window, grouped by feed slug.

    Each record's images are narrowed to its own strip folder. Records are
    deduplicated by canonical address (the earliest-recorded usable copy wins)
    and ordered by (strip date, canonical address), so same-date siblings come
    out in one fixed order whichever file saved them first.
    """
    files = find_tinyview_data_files(data_dir)
    if not files:
        return {}

    newest = files[-1][0]
    window_start = newest - timedelta(days=WINDOW_DAYS)
    logger.info(f"Strip window: {window_start} to {newest} (newest data file {files[-1][1].name})")

    strips: Dict[str, Tuple[date, dict]] = {}
    for file_date, path in files:
        # A strip is never dated after the file that saved it.
        if file_date < window_start:
            continue
        for position, record in enumerate(read_data_file(path)):
            try:
                strip_date, address, record = own_strip(record)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed record #{position} in {path}: {e!r}")
                continue
            if strip_date < window_start or not record['images'] or address in strips:
                continue
            strips[address] = (strip_date, record)

    grouped: Dict[str, List[dict]] = {}
    for address, (strip_date, record) in sorted(strips.items(), key=lambda item: (item[1][0], item[0])):
        grouped.setdefault(record['slug'], []).append(record)
    return grouped


def load_tinyview_comics_list(catalog_path) -> Dict[str, dict]:
    """Load TinyView comics metadata, keyed by feed slug."""
    try:
        with open(catalog_path, 'r') as f:
            comics = json.load(f)

        comics_dict = {comic['slug']: comic for comic in comics}
        logger.info(f"Loaded metadata for {len(comics_dict)} TinyView comics")

        return comics_dict
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
        return {}


def generate_feed_for_comic(slug, strips, comic_metadata, output_dir='public/feeds'):
    """Write one comic's feed from its usable strips. Returns True when written."""
    try:
        if slug not in comic_metadata:
            logger.warning(f"No metadata found for {slug}, skipping")
            return False

        comic_info = comic_metadata[slug].copy()
        comic_info['source'] = 'tinyview'

        feed_entries = []
        for strip in strips:
            if not strip.get('images'):
                continue

            # 23:59:59 so TinyView comics sort at the top of their day, just before
            # the next day's Comics Kingdom/GoComics entries.
            strip_date = parse_strip_date(strip['date'])
            pub_datetime = datetime(
                strip_date.year, strip_date.month, strip_date.day, 23, 59, 59, tzinfo=pytz.UTC
            )

            feed_entries.append({
                'title': strip.get('name', f"{comic_info['name']} - {strip['date']}"),
                'url': strip['url'],
                'pub_date': pub_datetime,
                'description': strip.get('description', ''),
                'image_url': strip['images'][0]['url'],
                'images': strip['images'],
            })

        # Never replace a feed with an empty one.
        if not feed_entries:
            logger.info(f"No usable strips for {slug}; leaving its feed untouched")
            return False

        feed_gen = ComicFeedGenerator(output_dir=str(output_dir))
        if feed_gen.generate_feed(comic_info, feed_entries):
            logger.info(f"Generated feed for {comic_info['name']} at {Path(output_dir) / f'{slug}.xml'} with {len(feed_entries)} entries")
            return True
        logger.error(f"Failed to generate feed for {comic_info['name']}")
        return False

    except Exception as e:
        logger.error(f"Error generating feed for {slug}: {e}")
        return False


def main(data_dir='data', output_dir='public/feeds', catalog_path='public/tinyview_comics_list.json'):
    """Generate every TinyView feed that has a usable strip in the window."""
    logger.info("=" * 80)
    logger.info("TinyView Feed Generation")
    logger.info("=" * 80)

    strips_by_slug = load_window_strips(data_dir)
    if not strips_by_slug:
        logger.error(f"No usable TinyView strips found in {data_dir}. Run the TinyView scraper first.")
        logger.info("\n⚠️  Skipping TinyView feed generation")
        return 0  # Exit successfully (don't fail the workflow)

    comics_metadata = load_tinyview_comics_list(catalog_path)
    if not comics_metadata:
        logger.error("Failed to load TinyView comics metadata")
        return 0  # Exit successfully

    logger.info(f"\nGenerating feeds for {len(strips_by_slug)} TinyView comics...")

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for slug, strips in sorted(strips_by_slug.items()):
        print(f"  Processing {slug}...", end=' ')

        if slug not in comics_metadata:
            logger.warning(f"No catalog entry for TinyView slug {slug}; skipping its {len(strips)} strip(s)")
            print("⚠️  No metadata")
            skipped_count += 1
            continue

        if generate_feed_for_comic(slug, strips, comics_metadata, output_dir):
            print(f"✅ {comics_metadata[slug]['name']} ({len(strips)} strips)")
            success_count += 1
        else:
            print("❌ Failed")
            failed_count += 1

    logger.info("\n" + "=" * 80)
    logger.info("✅ Feed Generation Complete!")
    logger.info("=" * 80)
    logger.info(f"Successful: {success_count}")
    logger.info(f"Skipped (no metadata): {skipped_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Total: {len(strips_by_slug)}")
    logger.info(f"\nFeeds saved to: {output_dir}/")
    logger.info("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
