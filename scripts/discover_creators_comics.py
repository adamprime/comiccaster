#!/usr/bin/env python3
"""Discover Creators comics and flag overlaps with existing ComicCaster catalogs."""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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
            time.sleep(1.0 * (attempt + 1))
    return None


def fetch_creators_catalog() -> List[Dict]:
    urls = [
        "https://www.creators.com/categories/comics/all",
        "https://www.creators.com/categories/comics/archive",
    ]

    by_slug: Dict[str, Dict] = {}
    for section_url in urls:
        response = request_with_retry(section_url)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.select('a[href^="/read/"]'):
            href = link.get("href", "")
            parts = href.strip("/").split("/")
            if len(parts) < 2 or parts[0] != "read":
                continue

            slug = parts[1]
            name = " ".join(link.get_text(" ", strip=True).split()) or slug.replace("-", " ").title()
            by_slug[slug] = {
                "slug": slug,
                "name": name,
                "source_url": f"https://www.creators.com/read/{slug}",
                "section": "archive" if section_url.endswith("/archive") else "all",
            }

    return list(by_slug.values())


def load_existing_catalogs() -> Dict[str, set]:
    base = Path(__file__).parent.parent
    catalogs = [
        base / "public/comics_list.json",
        base / "public/tinyview_comics_list.json",
        base / "scripts/political_comics_list.json",
    ]

    existing = []
    for path in catalogs:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                existing.extend(json.load(f))

    feeds_dir = base / "public/feeds"
    feed_slugs = {p.stem for p in feeds_dir.glob("*.xml")}

    return {
        "slugs": {item.get("slug") for item in existing if item.get("slug")},
        "names": {normalize(item.get("name", "")) for item in existing if item.get("name")},
        "feed_slugs": feed_slugs,
    }


def fetch_feature_meta(slug: str) -> Dict:
    read_url = f"https://www.creators.com/read/{slug}"
    response = request_with_retry(read_url)
    if not response:
        return {"feature_id": None, "release_counts": {}}

    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.find("body")
    feature_id = body.get("data-feature-id") if body else None
    if not feature_id:
        return {"feature_id": None, "release_counts": {}}

    year_now = datetime.now().year
    years = [year_now, year_now - 1]
    release_counts = {}
    for year in years:
        api_url = f"https://www.creators.com/api/features/get_release_dates?feature_id={feature_id}&year={year}"
        api_response = request_with_retry(api_url)
        if not api_response:
            release_counts[str(year)] = 0
            continue
        try:
            data = api_response.json()
            release_counts[str(year)] = len(data) if isinstance(data, list) else 0
        except Exception:
            release_counts[str(year)] = 0

    return {"feature_id": feature_id, "release_counts": release_counts}


def main() -> int:
    creators = fetch_creators_catalog()
    existing = load_existing_catalogs()

    print(f"Found {len(creators)} Creators comics")

    report = []
    for comic in sorted(creators, key=lambda c: c["name"].lower()):
        slug = comic["slug"]
        name_norm = normalize(comic["name"])

        slug_collision = slug in existing["slugs"] or slug in existing["feed_slugs"]
        name_overlap = name_norm in existing["names"]

        meta = fetch_feature_meta(slug)
        release_counts = meta["release_counts"]
        active_recently = sum(release_counts.values()) > 0

        report.append({
            **comic,
            "feature_id": meta["feature_id"],
            "release_counts": release_counts,
            "active_recently": active_recently,
            "slug_collision": slug_collision,
            "name_overlap": name_overlap,
            "recommended_slug": f"creators-{slug}" if slug_collision else slug,
            "eligible": active_recently and not (slug_collision or name_overlap),
        })

    total = len(report)
    overlaps = sum(1 for item in report if item["slug_collision"] or item["name_overlap"])
    eligible = [item for item in report if item["eligible"]]

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_creators_comics": total,
            "overlap_or_collision": overlaps,
            "eligible_unique_active": len(eligible),
        },
        "comics": report,
    }

    out_path = Path("data/creators_discovery_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Saved discovery report: {out_path}")
    print(f"Eligible unique+active comics: {len(eligible)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
