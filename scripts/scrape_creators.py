#!/usr/bin/env python3
"""Scrape Creators Syndicate comics into data/creators_$DATE.json.

No feed generation — see scripts/generate_creators_feeds.py for that.

Per comic: resolve the feature_id from the public read page, then page
through the release API until we've collected up to MAX_RELEASES_PER_COMIC
valid releases. Deduplication and missing-field filtering happen here so
the generator can consume the saved data without re-validating.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytz
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MAX_RELEASES_PER_COMIC = 30
CATALOG_PATH = Path("public/comics_list.json")
DATA_DIR = Path("data")


def request_with_retry(url):
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def load_creators_catalog():
    with open(CATALOG_PATH, encoding="utf-8") as f:
        all_comics = json.load(f)
    creators = [c for c in all_comics if c.get("source") == "creators"]
    logger.info(f"Found {len(creators)} Creators comics in catalog")
    return creators


def get_creators_slug(comic_info):
    """The creators.com slug (not our comic slug). Preserves prior behavior."""
    if comic_info.get("source_slug"):
        return comic_info["source_slug"]
    slug = comic_info.get("slug", "")
    if slug.startswith("creators-"):
        return slug.replace("creators-", "", 1)
    return slug


def resolve_feature_id(comic_info):
    creators_slug = get_creators_slug(comic_info)
    read_url = comic_info.get("url") or f"https://www.creators.com/read/{creators_slug}"
    response = request_with_retry(read_url)
    if not response:
        return None, read_url
    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.find("body")
    feature_id = body.get("data-feature-id") if body else None
    return feature_id, read_url


def fetch_raw_releases(feature_id, limit=MAX_RELEASES_PER_COMIC):
    """Page through the release API, filter, dedupe by formatted_url.

    Returns a list of raw release dicts (release_date, full, thumb,
    formatted_url, title) in the order received from the API.
    """
    collected = []
    seen_urls = set()
    page = 0
    while len(collected) < limit:
        api_url = f"https://www.creators.com/api/features/releases/{feature_id}/{page}"
        response = request_with_retry(api_url)
        if not response:
            break
        payload = response.json()
        releases = payload.get("releases") if isinstance(payload, dict) else None
        if not releases:
            break
        for release in releases:
            release_date = (release.get("release_date") or "")[:10]
            image_url = release.get("full") or release.get("thumb")
            entry_url = release.get("formatted_url")
            if not release_date or not image_url or not entry_url:
                continue
            if entry_url in seen_urls:
                continue
            seen_urls.add(entry_url)
            collected.append({
                "release_date": release_date,
                "full": release.get("full"),
                "thumb": release.get("thumb"),
                "formatted_url": entry_url,
                "title": release.get("title"),
            })
            if len(collected) >= limit:
                break
        # The API returns small pages; fewer than 4 releases means no more.
        if len(releases) < 4:
            break
        page += 1
    return collected


def save_snapshot(comics_data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    eastern = pytz.timezone("US/Eastern")
    date_str = datetime.now(eastern).strftime("%Y-%m-%d")
    out = DATA_DIR / f"creators_{date_str}.json"
    payload = {
        "scraped_at": datetime.now(pytz.UTC).isoformat(),
        "comics": comics_data,
    }
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Saved {len(comics_data)} Creators comics to {out}")
    return out


def main():
    logger.info("=" * 80)
    logger.info("Scraping Creators Syndicate comics")
    logger.info("=" * 80)

    comics = load_creators_catalog()
    if not comics:
        logger.info("No Creators comics in catalog; nothing to scrape")
        # Still write an empty snapshot so the invariant guard sees the file.
        save_snapshot([])
        return 0

    scraped = []
    fail_count = 0
    for comic in comics:
        slug = comic["slug"]
        logger.info(f"Scraping {slug}...")
        feature_id, read_url = resolve_feature_id(comic)
        if not feature_id:
            logger.warning(f"  could not resolve feature_id for {slug} at {read_url}")
            fail_count += 1
            continue
        releases = fetch_raw_releases(feature_id)
        logger.info(f"  got {len(releases)} releases")
        scraped.append({
            "slug": slug,
            "feature_id": feature_id,
            "read_url": read_url,
            "releases": releases,
        })

    save_snapshot(scraped)
    logger.info(f"Done: {len(scraped)} scraped, {fail_count} failed")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
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
