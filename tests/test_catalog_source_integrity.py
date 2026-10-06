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
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

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


# --- Daily vs political placement (R8) and Comics Kingdom loading (R9) -------
#
# The daily and political catalogs are two website tabs *and* two loader
# inputs. A slug listed in both is a comic its loaders may pick up twice: for
# Comics Kingdom that is a double scrape and a feed whose political flag
# depends on which entry ran last. Mallard Fillmore and Brilliant Mind of
# Edison Lee got into both lists because the Comics Kingdom loaders read only
# the daily list, so the political-only cartoonists were never scraped and the
# "fix" was to copy entries across.

DAILY = "comics_list.json"
POLITICAL = "political_comics_list.json"
# A derived UI filter list for the Spanish tab, not a loader input -- see
# docs/solutions/ui-bugs/spanish-ui-filter-missing-comics-source-list-mismatch.md.
SPANISH = "spanish_comics_list.json"

# GoComics strips deliberately listed on both tabs. The GoComics loader keys its
# work on scraped data, not on catalog entries, so a shared slug there is one
# feed. A Comics Kingdom slug can never be excused this way (KTD3): its loaders
# walk the catalog, so a shared slug is scraped twice.
DAILY_AND_POLITICAL_ALLOWLIST = frozenset(
    {"doonesbury", "tomthedancingbug", "brian-mcfadden", "think"}
)


def _catalog(filename):
    """The entries of one catalog file, as _entries() yields them."""
    return [comic for name, comic in _entries() if name == filename]


def _by_slug(catalog):
    return {comic["slug"]: comic for comic in catalog}


def _overlap_violations(daily, political, allowlist):
    """Slugs in both lists that the allowlist does not excuse.

    An allowlisted slug is only excused while it is GoComics-owned in *both*
    lists -- allowlisting a Comics Kingdom slug must not silence the check.
    """
    daily_by_slug, political_by_slug = _by_slug(daily), _by_slug(political)
    violations = []
    for slug in sorted(daily_by_slug.keys() & political_by_slug.keys()):
        sources = (
            f"daily source={_source_of(daily_by_slug[slug])}, "
            f"political source={_source_of(political_by_slug[slug])}"
        )
        if slug not in allowlist:
            violations.append(f"{slug}: listed in both, not an allowed exception ({sources})")
        elif not (
            _source_of(daily_by_slug[slug]) == GOCOMICS
            and _source_of(political_by_slug[slug]) == GOCOMICS
        ):
            violations.append(
                f"{slug}: allowlisted, but only GoComics strips may be in both ({sources})"
            )
    return violations


def _stale_allowlist(daily, political, allowlist):
    """Allowlisted slugs that are no longer in both lists."""
    in_both = _by_slug(daily).keys() & _by_slug(political).keys()
    return sorted(set(allowlist) - in_both)


def _ck_slugs(catalog):
    return [comic["slug"] for comic in catalog if comic.get("source") == "comicskingdom"]


def test_no_slug_is_in_both_daily_and_political_catalogs():
    """R8: each comic lives on one tab, bar four named GoComics strips."""
    violations = _overlap_violations(
        _catalog(DAILY), _catalog(POLITICAL), DAILY_AND_POLITICAL_ALLOWLIST
    )
    assert not violations, (
        f"Slugs listed in both {DAILY} and {POLITICAL}. Move each to the one tab "
        "it belongs on; a Comics Kingdom comic in both is scraped twice:\n  "
        + "\n  ".join(violations)
    )


def test_daily_and_political_allowlist_is_not_stale():
    """KTD3: an allowlisted slug that left one list must leave the allowlist."""
    stale = _stale_allowlist(_catalog(DAILY), _catalog(POLITICAL), DAILY_AND_POLITICAL_ALLOWLIST)
    assert not stale, (
        f"Allowlisted slugs no longer in both {DAILY} and {POLITICAL} -- drop them "
        f"from DAILY_AND_POLITICAL_ALLOWLIST: {stale}"
    )


@pytest.mark.parametrize(
    "daily, political, allowlist, flagged",
    [
        pytest.param(
            [{"slug": "ck-both", "source": "comicskingdom"}],
            [{"slug": "ck-both", "source": "comicskingdom"}],
            {"ck-both"},
            ["ck-both"],
            id="comicskingdom-slug-fails-even-when-allowlisted",
        ),
        pytest.param(
            [{"slug": "gc-ok"}, {"slug": "gc-bad", "source": "gocomics"}],
            [{"slug": "gc-ok", "source": ""}, {"slug": "gc-bad"}],
            {"gc-ok"},
            ["gc-bad"],
            id="allowlisted-gocomics-passes-unlisted-gocomics-fails",
        ),
        pytest.param(
            [{"slug": "mixed"}],
            [{"slug": "mixed", "source": "comicskingdom"}],
            {"mixed"},
            ["mixed"],
            id="allowlisted-slug-must-be-gocomics-in-both-lists",
        ),
    ],
)
def test_overlap_check_honours_the_allowlist_only_for_gocomics(daily, political, allowlist, flagged):
    """Pins the guard's own rule (KTD3), which the real catalogs cannot exercise."""
    violations = _overlap_violations(daily, political, allowlist)
    assert [v.split(":")[0] for v in violations] == flagged


def test_stale_allowlist_check_flags_a_slug_in_only_one_list():
    daily = [{"slug": "still-both"}, {"slug": "daily-only-now"}]
    political = [{"slug": "still-both"}]
    assert _stale_allowlist(daily, political, {"still-both", "daily-only-now"}) == ["daily-only-now"]


def _scraper_loader():
    import comicskingdom_scraper_individual

    return comicskingdom_scraper_individual.load_comics_catalog()


def _generator_loader():
    import generate_comicskingdom_feeds

    return generate_comicskingdom_feeds.load_comics_list()


CK_LOADERS = [
    pytest.param(_scraper_loader, id="scraper-load_comics_catalog"),
    pytest.param(_generator_loader, id="generator-load_comics_list"),
]


@pytest.mark.parametrize("load", CK_LOADERS)
def test_every_comicskingdom_entry_is_loaded_exactly_once(load, monkeypatch):
    """R4/R5/R9: both Comics Kingdom loaders cover both catalogs, once each.

    A catalog entry the loader skips is a comic that is listed on the site but
    never scraped -- its feed 404s. A slug returned twice is scraped twice.
    """
    expected = set(_ck_slugs(_catalog(DAILY))) | set(_ck_slugs(_catalog(POLITICAL)))

    monkeypatch.chdir(PROJECT_ROOT)
    loaded = [comic["slug"] for comic in load()]

    missing = sorted(expected - set(loaded))
    duplicated = sorted({slug for slug in loaded if loaded.count(slug) > 1})
    unexpected = sorted(set(loaded) - expected)
    assert not (missing or duplicated or unexpected), (
        f"Comics Kingdom loader disagrees with the source=comicskingdom entries in "
        f"{DAILY} + {POLITICAL} ({len(expected)} slugs):\n"
        f"  never loaded (listed on the site, never scraped): {missing}\n"
        f"  loaded more than once (scraped twice): {duplicated}\n"
        f"  loaded but not a Comics Kingdom catalog entry: {unexpected}"
    )


@pytest.mark.parametrize("load", CK_LOADERS)
def test_every_spanish_comicskingdom_entry_is_loaded(load, monkeypatch):
    """A Comics Kingdom comic on the Spanish tab must be one the loaders build.

    The Comics Kingdom loaders read only the daily and political catalogs, never
    the Spanish one. A Comics Kingdom entry that exists only in the Spanish list
    shows on the Spanish tab but is never scraped, so its feed 404s: the bug R9
    fixed for the political tab, coming back through a third list.
    """
    spanish = set(_ck_slugs(_catalog(SPANISH)))

    monkeypatch.chdir(PROJECT_ROOT)
    loaded = {comic["slug"] for comic in load()}

    never_loaded = sorted(spanish - loaded)
    assert not never_loaded, (
        f"source=comicskingdom entries in {SPANISH} that the Comics Kingdom loader "
        f"never loads (shown on the Spanish tab, never scraped, feed 404s): "
        f"{never_loaded}\n"
        f"{SPANISH} is a derived UI filter list the loaders do not read. Add each "
        f"comic to {DAILY} or {POLITICAL} (see docs/solutions/ui-bugs/"
        f"spanish-ui-filter-missing-comics-source-list-mismatch.md)."
    )


# --- Vintage reruns (#216) -------------------------------------------------
#
# 32 of Comics Kingdom's 33 vintage series are fixed archives that ComicCaster
# replays on its own schedule (comiccaster/comicskingdom_reruns.py). Bringing Up
# Father is vintage too, but Comics Kingdom still reposts it daily, so it must
# never be rerun.

REPOSTED_VINTAGE = {"bringing-up-father"}

# Daily and Sunday halves of one strip. Each pair shares its archive-to-delivery
# offset and its loop length, so a story's Sunday page arrives in the same week
# as its dailies, on every loop.
RERUN_PAIRS = [
    ("the-phantom-vintage", "the-phantom-vintage-sunday"),
    ("flash-gordon-vintage", "flash-gordon-vintage-sunday"),
    ("mandrake-the-magician-vintage", "mandrake-the-magician-vintage-sunday"),
    ("tiger-vintage", "tiger-vintage-sunday"),
]


def _rerun_entries():
    from comiccaster.comicskingdom_reruns import rerun_schedule
    return {comic["slug"]: rerun_schedule(comic)
            for _, comic in _entries() if rerun_schedule(comic) is not None}


def test_every_fixed_vintage_archive_is_rerun_and_nothing_else_is():
    fixed = {comic["slug"] for _, comic in _entries()
             if comic.get("source") == "comicskingdom"
             and comic.get("source_variant") == "vintage"
             and comic["slug"] not in REPOSTED_VINTAGE}
    rerun = set(_rerun_entries())
    assert len(fixed) == 32
    assert rerun == fixed, (
        f"fixed vintage archives without a rerun schedule: {sorted(fixed - rerun)}\n"
        f"rerun schedules on other comics: {sorted(rerun - fixed)}"
    )


def test_every_rerun_schedule_is_well_formed():
    urls = {comic["slug"]: comic["url"] for _, comic in _entries()}
    problems = []
    for slug, schedule in _rerun_entries().items():
        if schedule.start > schedule.end:
            problems.append(f"{slug}: start {schedule.start} is after end {schedule.end}")
        if schedule.anchor.weekday() != schedule.start.weekday():
            problems.append(f"{slug}: anchor {schedule.anchor} is not on the start's weekday")
        if urls[slug] != f"https://comicskingdom.com/vintage/{slug}":
            problems.append(f"{slug}: url {urls[slug]} is not its vintage archive")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("daily,sunday", RERUN_PAIRS)
def test_paired_daily_and_sunday_archives_stay_in_step(daily, sunday):
    schedules = _rerun_entries()
    d, s = schedules[daily], schedules[sunday]
    assert d.start - d.anchor == s.start - s.anchor, "the pair maps one delivery day to different archive weeks"
    assert d.loop_days == s.loop_days, "the pair would drift apart after the first loop"


def test_the_comicskingdom_loader_carries_the_rerun_fields(monkeypatch):
    from comiccaster.comicskingdom_catalog import load_comicskingdom_catalog
    from comiccaster.comicskingdom_reruns import rerun_schedule
    monkeypatch.chdir(PROJECT_ROOT)
    loaded = {comic["slug"]: comic for comic in load_comicskingdom_catalog("public")}
    assert rerun_schedule(loaded["beetle-bailey-vintage"]) == _rerun_entries()["beetle-bailey-vintage"]
    assert rerun_schedule(loaded["bringing-up-father"]) is None
