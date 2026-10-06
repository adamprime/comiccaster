#!/usr/bin/env python3
"""
Generate RSS feeds for Comics Kingdom comics from scraped data.

A Comics Kingdom dated page shows the newest post on or before its date, so the
scraper records the same strip every night it stays up. Since #216 each record
carries the displayed post's own date (``post_date``), and a feature has at most
one post per date, so a post-dated strip is identified by its comic and post
date, under the guid ``https://comicskingdom.com/<source slug>/<post date>``.

Records saved before #216 have no post date. For them a strip is still its image
set, dated by its first sighting: the earliest
``data/comicskingdom_YYYY-MM-DD.json`` holding it, read across all saved history
(issue #207).

- Each feed lists the strips dated in the 90 dates ending on the newest data
  file's date: post-dated strips by post date, older ones by first sighting.
  The window is anchored on the data, not the clock.
- A post-dated strip keeps its earliest record's images, so a published item
  does not change when Comics Kingdom later renames or splits its images. A
  backfill becomes the earliest record, so backfill a missed night promptly (the
  next day): a later one swaps the published item's images to the backfill's
  copies, under the same guid, so nothing is re-sent.
- Where an older item already holds a post-dated strip's address, the older
  record's saved name decides: no trailing date means the same strip and the
  published item stands; a trailing date means the older item is an earlier
  strip saved a night late, and the new strip is listed under its guid + #post.
- A comic with nothing in the window is not written at all: its existing feed
  file stays byte-identical and no new one is created.
- A vintage rerun record (``rerun_date``, comiccaster/comicskingdom_reruns.py)
  is one strip per comic and delivery night, guid
  ``ck-rerun-<slug>-<delivery date>``, listed only when the archive had a strip
  of its own that date. Once a series has a rerun in the window, its feed lists
  reruns only.

Records saved before #216 still rest on first sighting, so until the last of
them leaves the window, never overwrite, relabel or delete an existing Comics
Kingdom data file. Backfilling a missing night is safe only on or after the
first post-dated data file. A missing night from before then stays a gap until
it leaves the 90-date window: backfilling it would re-send, under their post
dates, strips that older records saved a night late.
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

# A record saved before post dates took its name from the page title, which ends
# in a date exactly when the page had no post of its own for the requested date.
DATED_NAME = re.compile(r' \d{4}-\d{2}-\d{2}$')


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


def _is_exact_date(value) -> bool:
    """True for a YYYY-MM-DD date. strptime alone accepts '2026-10-1', which would make a second guid."""
    try:
        return datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d') == value
    except (TypeError, ValueError):
        return False


def check_record(record) -> None:
    """Raise ValueError unless the record has the fields an item is built from."""
    if not isinstance(record, dict):
        raise ValueError(f"not a record: {record!r:.80}")
    for field in ('slug', 'url', 'date'):
        if not isinstance(record.get(field), str):
            raise ValueError(f"{field} missing or not text")
    datetime.strptime(record['date'], '%Y-%m-%d')
    if 'image_urls' in record:
        urls = record['image_urls']
        if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
            raise ValueError("image_urls is not a list of text")
    elif 'image_url' in record and not isinstance(record['image_url'], str):
        raise ValueError("image_url is not text")
    for field in ('post_date', 'rerun_date'):
        if field in record and not _is_exact_date(record[field]):
            raise ValueError(f"{field} is not a YYYY-MM-DD date: {record[field]!r:.40}")


def load_window_strips(
    files: List[Tuple[date, Path]]
) -> Tuple[Dict[str, List[Dict]], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    """The strips each comic lists in the window, as three dicts by slug, oldest first.

    Every file is read, oldest first.

    - Rerun records (``rerun_date``, checked before anything else): one item per
      slug and delivery night, listed when its file is in the window and the
      archive had a strip of its own that date. A gap record carries an earlier
      post and no images, and is never listed.

    - Old records (no ``post_date``): the first record holding a slug's image set
      is that strip's first sighting, listed when its file is in the window.
      Later copies of the set are ignored.
    - Post-dated records: one strip per slug and post date, listed when the post
      date is in the window. The earliest file's record supplies the images, so an
      item never changes once published.
    """
    newest = files[-1][0]
    window_start = newest - timedelta(days=WINDOW_DAYS - 1)
    print(f"📂 Reading {len(files)} Comics Kingdom data file(s); "
          f"window {window_start} to {newest} (newest data file {files[-1][1].name})")

    first_sightings: Dict[Tuple[str, Tuple[str, ...]], Tuple[date, Dict]] = {}
    posts: Dict[Tuple[str, str], Dict] = {}
    reruns: Dict[str, List[Dict]] = {}
    for file_date, path in files:
        for position, record in enumerate(read_data_file(path)):
            try:
                check_record(record)
            except ValueError as e:
                logger.warning(f"Skipping malformed record #{position} in {path}: {e}")
                continue
            images = image_urls(record)
            if 'rerun_date' in record:
                if images and record['post_date'] == record['rerun_date'] and file_date >= window_start:
                    reruns.setdefault(record['slug'], []).append(record)
                continue
            if not images:
                continue
            if 'post_date' in record:
                posts.setdefault((record['slug'], record['post_date']), record)
                continue
            key = (record['slug'], tuple(sorted(images)))
            if key not in first_sightings:
                first_sightings[key] = (file_date, record)

    # Files are read oldest first, so first sightings are already in date order.
    old: Dict[str, List[Dict]] = {}
    for (slug, _), (file_date, record) in first_sightings.items():
        if file_date >= window_start:
            old.setdefault(slug, []).append(record)

    posted: Dict[str, List[Dict]] = {}
    for (slug, post_date), record in sorted(posts.items()):
        if date.fromisoformat(post_date) >= window_start:
            posted.setdefault(slug, []).append(record)
    return old, posted, reruns


def load_comics_list(catalog_dir='public') -> List[Dict]:
    """Load Comics Kingdom comics from the daily and political catalogs."""
    ck_comics = load_comicskingdom_catalog(catalog_dir)

    print(f"✅ Found {len(ck_comics)} Comics Kingdom comics in catalog (daily + political)")
    return ck_comics


def strip_entry(comic_info: Dict, strip: Dict, day: str, link: str, guid: str) -> Dict:
    """One feed item for a strip, dated ``day`` (YYYY-MM-DD)."""
    urls = image_urls(strip)
    if 'image_urls' in strip:
        images = [{'url': url, 'alt': f"{comic_info['name']} - Panel {i + 1}"}
                  for i, url in enumerate(urls)]
    else:
        images = [{'url': urls[0], 'alt': comic_info['name']}]
    return {
        'title': f"{comic_info['name']} - {day}",
        'url': link,
        'images': images,
        'pub_date': datetime.strptime(day, '%Y-%m-%d').replace(tzinfo=pytz.UTC),
        'description': f"Comic strip for {day}",
        'id': guid,
    }


def rerun_entries(comic_info: Dict, reruns: List[Dict]) -> List[Dict]:
    """One item per delivered rerun, identified by its comic and delivery date.

    Guid ``ck-rerun-<slug>-<delivery date>``, so a later loop that delivers the
    same archive date again is a new item. Link: the strip's archive page. The
    title and description carry the print date; pubDate is the delivery date.
    """
    source_slug = comic_info.get('source_slug') or comic_info['slug']
    entries = []
    for strip in reruns:
        link = f"https://comicskingdom.com/vintage/{source_slug}/{strip['rerun_date']}"
        guid = f"ck-rerun-{comic_info['slug']}-{strip['date']}"
        entry = strip_entry(comic_info, strip, strip['rerun_date'], link, guid)
        entry['pub_date'] = datetime.strptime(strip['date'], '%Y-%m-%d').replace(tzinfo=pytz.UTC)
        entries.append(entry)
    return entries


def feed_entries(comic_info: Dict, old_strips: List[Dict], posted_strips: List[Dict],
                 reruns: List[Dict] = ()) -> List[Dict]:
    """One comic's items: its old first sightings, then its post-dated strips.

    A rerun series with a delivered rerun in the window lists its reruns only,
    so the frozen strip it showed every night before go-live drops out.

    A post-dated strip's guid and link are ``https://comicskingdom.com/<source
    slug>/<post date>``. When an old item already holds that guid, the old
    record's saved name decides, never the image sets:

    - no trailing date: the old page had a post of its own that night, so it is
      the same strip and the published item stands alone;
    - a trailing date: the old item holds an earlier strip saved a night late, so
      the post-dated strip is listed as well, under its guid plus ``#post``.
    """
    if reruns:
        return rerun_entries(comic_info, reruns)

    entries = [strip_entry(comic_info, strip, strip['date'], strip['url'], strip['url'])
               for strip in old_strips]

    # The first old item with a guid is the one the feed keeps.
    old_names: Dict[str, object] = {}
    for strip in old_strips:
        old_names.setdefault(strip['url'], strip.get('name'))

    source_slug = comic_info.get('source_slug') or comic_info['slug']
    for strip in posted_strips:
        link = f"https://comicskingdom.com/{source_slug}/{strip['post_date']}"
        guid = link
        if guid in old_names:
            name = old_names[guid]
            if not (isinstance(name, str) and DATED_NAME.search(name)):
                continue
            guid += '#post'
        entries.append(strip_entry(comic_info, strip, strip['post_date'], link, guid))
    return entries


def generate_feed_for_comic(comic_info: Dict, old_strips: List[Dict], posted_strips: List[Dict],
                            generator: ComicFeedGenerator, reruns: List[Dict] = ()) -> bool:
    """Write one comic's feed from its strips in the window. Returns True when written.

    With no strip to list the feed is not written, so an existing file stays as it is.
    """
    entries = feed_entries(comic_info, old_strips, posted_strips, reruns)

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
    """Generate every Comics Kingdom feed with a strip to list in the window."""
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
    old_by_slug, posted_by_slug, reruns_by_slug = load_window_strips(files)
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
    failed = 0

    for comic in comics_list:
        old_strips = old_by_slug.get(comic['slug'], [])
        posted_strips = posted_by_slug.get(comic['slug'], [])
        reruns = reruns_by_slug.get(comic['slug'], [])
        if not old_strips and not posted_strips and not reruns:
            untouched += 1
        elif generate_feed_for_comic(comic, old_strips, posted_strips, generator, reruns):
            written += 1
        else:
            failed += 1

    print()
    print("="*80)
    print("✅ Feed Generation Complete!")
    print("="*80)
    print(f"Written: {written}")
    print(f"Untouched (no strip to list in the window): {untouched}")
    print(f"Failed: {failed}")
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
