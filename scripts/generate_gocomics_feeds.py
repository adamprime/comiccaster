#!/usr/bin/env python3
"""
Generate RSS feeds for GoComics comics from Phase 1 scraped data.

This script:
1. Loads scraped GoComics data from data/comics_YYYY-MM-DD.json (Phase 1 output)
2. Loads the comic catalog (regular + political)
3. Generates/updates RSS feeds for each comic that has scraped data

This replaces the old approach in update_feeds.py which re-fetched every comic
individually with high concurrency, which became unreliable.
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from comiccaster.feed_generator import ComicFeedGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_scraped_data(days_back: int = 90) -> Dict[str, List[Dict]]:
    """Load scraped GoComics data from multiple days and group by slug.

    Args:
        days_back: Number of days of data files to load.

    Returns:
        Dict mapping slug -> list of comic entries.
    """
    data_dir = Path('data')
    data_files = sorted(data_dir.glob('comics_*.json'), reverse=True)

    if not data_files:
        logger.error("No GoComics data files found in data/")
        return {}

    files_to_load = data_files[:days_back]

    logger.info(f"Loading GoComics data from {len(files_to_load)} day(s)...")

    indexed: Dict[str, List[Dict]] = {}
    seen_slug_dates: set = set()
    total_loaded = 0
    duplicates_skipped = 0

    for data_file in files_to_load:
        date_from_file = data_file.stem.replace('comics_', '')

        try:
            with open(data_file, 'r') as f:
                comics = json.load(f)

            for comic in comics:
                slug = comic.get('slug')
                date = comic.get('date', date_from_file)
                if not slug:
                    continue

                key = (slug, date)
                if key in seen_slug_dates:
                    duplicates_skipped += 1
                    logger.debug(
                        f"Skipping duplicate entry for {slug} on {date}"
                    )
                    continue
                seen_slug_dates.add(key)

                if slug not in indexed:
                    indexed[slug] = []
                indexed[slug].append(comic)
                total_loaded += 1

            logger.info(f"  {date_from_file}: {len(comics)} comics")
        except Exception as e:
            logger.warning(f"Error loading {data_file.name}: {e}")

    if duplicates_skipped:
        logger.warning(
            f"Skipped {duplicates_skipped} duplicate slug/date entries "
            f"(likely Spanish/English overlap in scraped data)"
        )

    logger.info(f"Loaded {total_loaded} total entries for {len(indexed)} unique comics")
    return indexed


def load_comics_catalog() -> List[Dict]:
    """Load the full GoComics catalog (regular + political comics)."""
    comics = []

    comics_file = Path('comics_list.json')
    try:
        with open(comics_file, 'r') as f:
            comics.extend(json.load(f))
    except Exception as e:
        logger.error(f"Error loading {comics_file}: {e}")
        return []

    political_file = Path(__file__).parent / 'political_comics_list.json'
    try:
        if political_file.exists():
            with open(political_file, 'r') as f:
                political = json.load(f)
                comics.extend(political)
                logger.info(f"Loaded {len(political)} political comics")
    except Exception as e:
        logger.warning(f"Error loading political comics: {e}")

    logger.info(f"Total catalog: {len(comics)} comics")
    return comics


def generate_feed_for_comic(
    comic_info: Dict,
    scraped_data: Dict[str, List[Dict]],
    generator: ComicFeedGenerator,
) -> bool:
    """Generate a feed for a single comic from scraped data.

    Returns True if feed was generated, False if no data available.
    """
    slug = comic_info['slug']

    if slug not in scraped_data:
        return False

    comic_entries = scraped_data[slug]

    # Sort by date (oldest first) and deduplicate by URL
    comic_entries_sorted = sorted(comic_entries, key=lambda x: x.get('date', ''))

    entries = []
    seen_urls = set()

    for scraped in comic_entries_sorted:
        image_url = scraped.get('image_url')
        comic_url = scraped.get('url', '')

        if not image_url or not comic_url:
            continue

        if comic_url in seen_urls:
            continue
        seen_urls.add(comic_url)

        try:
            pub_date = datetime.strptime(scraped['date'], '%Y-%m-%d').replace(tzinfo=pytz.UTC)
        except (ValueError, KeyError):
            continue

        entries.append({
            'title': f"{comic_info['name']} - {scraped['date']}",
            'url': comic_url,
            'images': [{'url': image_url, 'alt': comic_info['name']}],
            'pub_date': pub_date,
            'description': f"Comic strip for {scraped['date']}",
            'id': comic_url,
        })

    if not entries:
        return False

    # Oldest first -- feedgen produces newest-first output
    entries.sort(key=lambda x: x['pub_date'])

    try:
        return generator.generate_feed(comic_info, entries)
    except Exception as e:
        logger.error(f"Error generating feed for {comic_info['name']}: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("GoComics Feed Generator (from scraped data)")
    logger.info("=" * 60)

    scraped_data = load_scraped_data()
    if not scraped_data:
        logger.error("No scraped data available. Run Phase 1 data collection first.")
        return 1

    catalog = load_comics_catalog()
    if not catalog:
        logger.error("No comics in catalog")
        return 1

    generator = ComicFeedGenerator(
        base_url="https://www.gocomics.com",
        output_dir="public/feeds",
    )

    successful = 0
    skipped = 0

    for comic in catalog:
        if generate_feed_for_comic(comic, scraped_data, generator):
            successful += 1
        else:
            skipped += 1

    logger.info("=" * 60)
    logger.info("GoComics Feed Generation Complete")
    logger.info(f"  Updated: {successful}")
    logger.info(f"  Skipped (no data): {skipped}")
    logger.info(f"  Total catalog: {len(catalog)}")
    logger.info("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
