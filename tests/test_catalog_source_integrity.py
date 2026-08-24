"""Catalog integrity: one comic, one source, one feed file.

Every self-hosted feed lives at ``public/feeds/<slug>.xml`` (CONCEPTS.md,
"Self-hosted-feed source"), and each comic carries a single ``source`` tag that
selects how it is fetched. Those two facts together mean a slug may be claimed
by at most one feed-generating source -- otherwise two generators write the same
path and the last one to run silently wins.

That is not hypothetical. ``shoe``, ``broomhilda``, ``edge-city`` and
``pluggers`` were scraped by both GoComics and Comics Kingdom, so Pass 1 (which
ends with Comics Kingdom) and Pass 2 (which runs GoComics alone) overwrote each
other every single day, and subscribers received each strip twice from
alternating sources.

The root cause was a catalog edit, not scraper logic: commit 11e401b688
("Add all Comics Kingdom comics", 2025-11-15) stamped ``source: comicskingdom``
onto entries that already existed as GoComics comics and left their ``url``
pointing at gocomics.com. These tests encode the invariant that edit broke.
"""

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
PUBLIC = PROJECT_ROOT / "public"

CATALOG_FILES = [
    "comics_list.json",
    "political_comics_list.json",
    "spanish_comics_list.json",
    "tinyview_comics_list.json",
    "farside_comics_list.json",
    "newyorker_comics_list.json",
    "external_comics_list.json",
]

# A comic with no `source` is a GoComics comic -- that is how the catalog has
# always marked them, and 463 entries rely on it.
GOCOMICS = "gocomics"

# The host a source's `url` must point at. An entry whose source and url
# disagree is the exact fingerprint of the 2025-11-15 bulk stamp.
SOURCE_HOST = {
    GOCOMICS: "gocomics.com",
    "comicskingdom": "comicskingdom.com",
    "creators": "creators.com",
    "tinyview": "tinyview.com",
    "newyorker": "newyorker.com",
    "farside-daily": "thefarside.com",
    "farside-new": "thefarside.com",
    "mrboffo": "mrboffocomics.com",
}

# External-RSS sources are exempt from both checks: ComicCaster generates no
# feed for them (so they cannot collide on a feed path) and their url points at
# the publisher's own site by definition.
EXTERNAL = "external-rss"


def _entries():
    """Yield (catalog_filename, comic_dict) for every catalog entry."""
    for name in CATALOG_FILES:
        path = PUBLIC / name
        if not path.exists():
            continue
        for comic in json.loads(path.read_text()):
            if isinstance(comic, dict) and comic.get("slug"):
                yield name, comic


def _source_of(comic):
    return comic.get("source") or GOCOMICS


def test_every_catalog_entry_declares_a_known_source():
    """An unrecognised source has no generator and no host mapping."""
    known = set(SOURCE_HOST) | {EXTERNAL}
    unknown = {
        (name, comic["slug"], _source_of(comic))
        for name, comic in _entries()
        if _source_of(comic) not in known
    }
    assert not unknown, f"Catalog entries with an unknown source: {sorted(unknown)}"


def test_source_and_url_agree():
    """A comic's `url` must point at the host its `source` names.

    This is the check that would have caught commit 11e401b688 the day it
    landed: it stamped source=comicskingdom onto entries whose url still read
    https://www.gocomics.com/..., and nothing objected for nine months.
    """
    mismatches = []
    for name, comic in _entries():
        source = _source_of(comic)
        if source == EXTERNAL:
            continue
        expected = SOURCE_HOST[source]
        host = (urlparse(comic.get("url") or "").netloc or "").lower()
        host = host[4:] if host.startswith("www.") else host
        if host and host != expected:
            mismatches.append(f"{name}:{comic['slug']} source={source} url-host={host} (want {expected})")
    assert not mismatches, (
        "Catalog entries whose source and url disagree -- one of them is wrong, "
        "and whichever it is, the comic is being fetched or linked from the "
        "wrong place:\n  " + "\n  ".join(sorted(mismatches))
    )


def test_no_slug_is_claimed_by_two_feed_generating_sources():
    """Two generators must never be able to write the same feed file.

    Only feed-generating sources count: external-rss produces no
    public/feeds/<slug>.xml, so an overlap with it cannot clobber anything.
    """
    owners = {}
    for name, comic in _entries():
        source = _source_of(comic)
        if source == EXTERNAL:
            continue
        owners.setdefault(comic["slug"], {}).setdefault(source, set()).add(name)

    contested = {
        slug: {src: sorted(files) for src, files in by_source.items()}
        for slug, by_source in owners.items()
        if len(by_source) > 1
    }
    assert not contested, (
        "Slugs claimed by more than one feed-generating source. Both generators "
        "write public/feeds/<slug>.xml, so whichever runs last wins and the feed "
        "flips source between passes:\n  "
        + "\n  ".join(f"{slug}: {claims}" for slug, claims in sorted(contested.items()))
    )
