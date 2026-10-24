#!/usr/bin/env python3
"""Build public/catalog.json: one machine-readable list of every comic offered.

The site's catalog is seven tab lists (public/*comics_list.json) with seven
different key sets, and only the external list carries a feed URL. Agents
should not have to reconcile them or scrape index.html, so this writes one
document with one schema per comic:

    slug, name, author, source, category, language,
    feed_url, site_url, has_feed, last_updated

`category` is the tab a comic is listed on. A comic in the Daily list and a
more specific one (Spanish, Political, Far Side, New Yorker) is one feed and
one entry, in the specific category; its name, author and site URL come from
the Daily list. `language` is the one the comic's entry declares (the Daily
list says `es` for every Spanish-tab comic), else `en`: the same field the feed
generator writes as the feed's <language>. An external-RSS comic is a separate entry even when a hosted
feed shares its slug, so `feed_url` is the unique key, not `slug`.

A listed comic with no public/feeds/<slug>.xml (upstream-dormant ones, which
the site still lists) has `has_feed: false` and no `feed_url`, so an agent never
hands out a 404. A feed file no list claims is left out and logged.

`last_updated` is the feed's lastBuildDate in UTC; null for external feeds,
which are not fetched. The Far Side morning pass rewrites farside-daily.xml
without rebuilding this file, so that one entry can trail by up to a day.

Network-free and deterministic (no build timestamp): Phase 2 of Pass 1 and
Pass 2 runs it after the feed generators, and so does their push recovery.
"""

import json
import logging
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

SITE = 'https://comiccaster.xyz'

# Lists of comics whose feeds ComicCaster hosts, least specific first: a comic
# in more than one takes the category of the last.
HOSTED_LISTS = [
    ('comics_list.json', 'daily'),
    ('political_comics_list.json', 'political'),
    ('spanish_comics_list.json', 'spanish'),
    ('tinyview_comics_list.json', 'tinyview'),
    ('farside_comics_list.json', 'farside'),
    ('newyorker_comics_list.json', 'newyorker'),
]
EXTERNAL_LIST = 'external_comics_list.json'

# A comic with no `source` is a GoComics comic (see test_catalog_source_integrity).
GOCOMICS = 'gocomics'


def _read_list(path):
    with open(path, encoding='utf-8') as f:
        return [c for c in json.load(f) if isinstance(c, dict) and c.get('slug')]


def last_build_date(feed_path):
    """The feed's lastBuildDate as ISO 8601 UTC, or None if it can't be read.

    Stops at the first <item>: lastBuildDate is a channel element ahead of the
    items, and some feeds hold months of them.
    """
    try:
        with open(feed_path, 'rb') as f:
            for _, elem in ET.iterparse(f):
                if elem.tag == 'lastBuildDate':
                    built = parsedate_to_datetime(elem.text.strip())
                    if built.tzinfo is None:  # RFC 2822 "-0000": UTC, zone unstated
                        built = built.replace(tzinfo=timezone.utc)
                    return built.astimezone(timezone.utc).isoformat()
                if elem.tag == 'item':
                    break
    except (ET.ParseError, OSError, AttributeError, TypeError, ValueError) as e:
        logger.warning(f"Unreadable lastBuildDate in {feed_path}: {e}")
        return None
    logger.warning(f"No lastBuildDate in {feed_path}")
    return None


def _entry(slug, name, author, source, category, language, feed_url, site_url, has_feed, last_updated):
    return {
        'slug': slug,
        'name': name,
        'author': author or None,
        'source': source,
        'category': category,
        'language': language or 'en',
        'feed_url': feed_url,
        'site_url': site_url or None,
        'has_feed': has_feed,
        'last_updated': last_updated,
    }


def _hosted_entries(public_dir):
    merged = {}
    for filename, category in HOSTED_LISTS:
        for comic in _read_list(public_dir / filename):
            fields = merged.setdefault(comic['slug'], {
                'name': comic['name'],
                'author': comic.get('author'),
                'source': comic.get('source') or GOCOMICS,
                'site_url': comic.get('url'),
                'language': comic.get('language'),
            })
            for key, value in (('author', comic.get('author')), ('site_url', comic.get('url')),
                               ('language', comic.get('language'))):
                fields[key] = fields[key] or value
            fields['category'] = category

    for slug, fields in merged.items():
        feed_path = public_dir / 'feeds' / f'{slug}.xml'
        has_feed = feed_path.is_file()
        yield _entry(
            slug, fields['name'], fields['author'], fields['source'], fields['category'],
            fields['language'],
            feed_url=f'{SITE}/feeds/{slug}.xml' if has_feed else None,
            site_url=fields['site_url'],
            has_feed=has_feed,
            last_updated=last_build_date(feed_path) if has_feed else None,
        )


def _external_entries(public_dir):
    for comic in _read_list(public_dir / EXTERNAL_LIST):
        yield _entry(
            comic['slug'], comic['name'], comic.get('author'), comic['source'], 'external',
            comic.get('language'),
            feed_url=comic['feed_url'],
            site_url=comic.get('url'),
            has_feed=True,
            last_updated=None,
        )


def build_catalog(public_dir):
    """The catalog document for the lists and feeds under public_dir."""
    public_dir = Path(public_dir)
    comics = [*_hosted_entries(public_dir), *_external_entries(public_dir)]
    comics.sort(key=lambda c: (c['name'].casefold(), c['source'], c['slug']))
    return {
        'site': SITE,
        'docs': f'{SITE}/llms.txt',
        'count': len(comics),
        'comics': comics,
    }


def unlisted_feeds(public_dir, catalog):
    """Slugs of public/feeds/*.xml files that no hosted catalog entry claims."""
    listed = {c['slug'] for c in catalog['comics'] if c['source'] != 'external-rss'}
    return sorted(p.stem for p in (Path(public_dir) / 'feeds').glob('*.xml') if p.stem not in listed)


def write_catalog(catalog, path):
    """Write atomically, so Netlify never serves a half-written catalog."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.catalog-', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.chmod(tmp, 0o644)  # mkstemp creates 0600; the site files are world-readable
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def main(public_dir='public'):
    public_dir = Path(public_dir)
    try:
        catalog = build_catalog(public_dir)
        write_catalog(catalog, public_dir / 'catalog.json')
    except (OSError, ValueError, KeyError) as e:
        logger.error(f"Catalog not rebuilt; the previous one stays: {e}")
        return 1

    for slug in unlisted_feeds(public_dir, catalog):
        logger.warning(f"public/feeds/{slug}.xml is in no comic list; left out of the catalog")
    with_feed = sum(c['has_feed'] for c in catalog['comics'])
    logger.info(
        f"Wrote {public_dir / 'catalog.json'}: {catalog['count']} comics, "
        f"{with_feed} with a feed, {catalog['count'] - with_feed} listed without one"
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
