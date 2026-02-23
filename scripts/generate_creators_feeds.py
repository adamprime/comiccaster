#!/usr/bin/env python3
"""Generate RSS feeds for Creators comics listed in the catalog."""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytz
import requests
from bs4 import BeautifulSoup

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from comiccaster.feed_generator import ComicFeedGenerator


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MAX_ENTRIES_PER_FEED = 30


def request_with_retry(url: str) -> Optional[requests.Response]:
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


def load_creators_comics() -> List[Dict]:
    comics_file = Path("public/comics_list.json")
    with open(comics_file, "r", encoding="utf-8") as f:
        all_comics = json.load(f)
    creators = [comic for comic in all_comics if comic.get("source") == "creators"]
    print(f"✅ Found {len(creators)} Creators comics in catalog")
    return creators


def get_creators_slug(comic_info: Dict) -> str:
    if comic_info.get("source_slug"):
        return comic_info["source_slug"]
    slug = comic_info.get("slug", "")
    if slug.startswith("creators-"):
        return slug.replace("creators-", "", 1)
    return slug


def resolve_feature_id(comic_info: Dict) -> Tuple[Optional[str], Optional[str]]:
    creators_slug = get_creators_slug(comic_info)
    read_url = comic_info.get("url") or f"https://www.creators.com/read/{creators_slug}"
    response = request_with_retry(read_url)
    if not response:
        return None, read_url

    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.find("body")
    feature_id = body.get("data-feature-id") if body else None
    return feature_id, read_url


def fetch_releases(feature_id: str, comic_info: Dict, limit: int = MAX_ENTRIES_PER_FEED) -> List[Dict]:
    entries: List[Dict] = []
    seen_urls = set()
    page = 0

    while len(entries) < limit:
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

            if len(entries) >= limit:
                break

        if len(releases) < 4:
            break

        page += 1

    entries.sort(key=lambda x: x["pub_date"])
    return entries


def generate_feed_for_comic(comic_info: Dict, generator: ComicFeedGenerator) -> bool:
    feature_id, read_url = resolve_feature_id(comic_info)
    if not feature_id:
        print(f"  ⚠️  Could not resolve feature id for {comic_info['slug']} ({read_url})")
        return False

    entries = fetch_releases(feature_id, comic_info)
    if not entries:
        print(f"  ⚠️  No entries found for {comic_info['name']}")
        return False

    success = generator.generate_feed(comic_info, entries)
    if success:
        print(f"  ✅ {comic_info['name']} ({len(entries)} entries)")
    else:
        print(f"  ❌ Failed: {comic_info['name']}")
    return success


def main() -> int:
    print("=" * 80)
    print("Creators Feed Generator")
    print("=" * 80)
    print()

    comics_list = load_creators_comics()
    if not comics_list:
        print("ℹ️  No Creators comics in catalog")
        return 0

    generator = ComicFeedGenerator(base_url="https://www.creators.com", output_dir="public/feeds")

    successful = 0
    failed = 0
    for comic in comics_list:
        if generate_feed_for_comic(comic, generator):
            successful += 1
        else:
            failed += 1

    print()
    print("=" * 80)
    print("✅ Feed Generation Complete!")
    print("=" * 80)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(comics_list)}")
    print("Feeds saved to: public/feeds/")
    return 0 if successful > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
