---
title: "GoComics slug extraction: badge filenames to href-based canonical links"
date: 2026-03-31
category: logic-errors
tags: [scraping, slug-extraction, gocomics, spanish-contamination, data-integrity, url-validation, codeql]
stack: [python, beautifulsoup, selenium, feedgen]
github_issues: [103, 104]
codeql_alerts: [49, 50, 51, 52]
---

## Problem

- **Spanish comic strips appearing in English RSS feeds** (GitHub #103): GoComics serves both English and Spanish versions of popular comics (e.g., `calvinandhobbes` and `calvinandhobbesespanol`). The scraper conflated them because it derived the comic slug from badge image filenames -- and both language versions share the same badge name.
- **FoxTrot showing daily Spanish strips instead of Sunday-only English** (GitHub #104): FoxTrot (English) only publishes on Sundays, but FoxTrot en Espanol publishes daily. Because badge names collided, the daily Spanish strips overwrote the weekly English feed.
- **142 comics silently dropped** due to slug mismatch: Badge-derived slugs (e.g., `baby-blues`) didn't match catalog slugs (e.g., `babyblues`), so the feed generator quietly skipped them.

## Root Cause

The old scraper used a **parallel-list, index-based** approach: it found all badge images on the page separately from all strip images, then zipped them together by position. The slug was derived from the badge filename (e.g., `Global_Feature_Badge_Calvin_And_Hobbes_600_abc.png` -> `calvin-and-hobbes`). This had two fatal flaws:

1. **Badge names aren't unique** -- English and Spanish versions of a comic share the same badge image filename. When zipped by index, the Spanish strip could overwrite the English entry.
2. **Badge names don't match URL slugs** -- GoComics URL slugs are concatenated without hyphens (e.g., `calvinandhobbes`), but badge filenames use underscores converted to hyphens. This mismatch caused 142 comics to be silently dropped during feed generation.

## Investigation Steps

1. Analyzed scraped JSON data files -- found 284 entries for 257 unique slugs (27 duplicates with different image URLs but same slug).
2. Traced through scraper code and identified the parallel-list zip approach as the source of incorrect pairing.
3. Examined saved HTML from GoComics profile pages to understand the DOM structure -- each comic lives inside a container div with its own link and images.
4. Compared with Comics Kingdom scraper, which already used a container-based approach (href-derived slugs).
5. Analyzed feed output to confirm Spanish strips were contaminating English feeds.

## Solution

### 1. Container-based slug extraction

Instead of deriving slugs from badge filenames, extract them from the canonical `<a href>` within each comic container:

```python
def _extract_comic_slug_from_link(href):
    parsed = urlparse(href)
    is_absolute_gc = (
        parsed.netloc in ('www.gocomics.com', 'gocomics.com')
        or parsed.netloc.endswith('.gocomics.com')
    )
    is_relative = not parsed.netloc and href.startswith('/') and not href.startswith('//')
    if not is_absolute_gc and not is_relative:
        return None
    if '/profile/' in href or '/_next/' in href or href.startswith('/api/'):
        return None
    slug = parsed.path.strip('/')
    return slug if slug else None
```

### 2. Proper URL domain validation (CodeQL fix)

Replaced substring-based URL checks (`'featureassets.gocomics.com' in url`) with proper domain parsing:

```python
def _is_asset_host(url):
    try:
        netloc = urlparse(url).netloc
        return netloc == 'featureassets.gocomics.com'
    except Exception:
        return False
```

### 3. Container iteration

The main extraction function iterates containers instead of zipping parallel lists. Each container's slug, strip image, and badge are extracted together, guaranteeing correct pairing regardless of page order or language variants.

### 4. Deduplication in feed generator

Added `seen_slug_dates` set in `generate_gocomics_feeds.py` to prevent duplicate entries when loading multi-day scraped data.

### 5. Data cleanup

- Cleaned 5,230 contaminated entries from old scraped JSON data files
- Reverted all GoComics feeds to pre-contamination state from git history (March 30 commit)
- Ran backfill to append 2 days of clean data (306 feeds updated, 0 failures)

## Verification

- **257 comics** correctly extracted per scrape run (up from ~115)
- **312 feeds** updated and verified clean of Spanish contamination
- **24 new tests** in `tests/test_authenticated_scraper.py` covering slug extraction (absolute/relative URLs, rejection of non-comic URLs), image source validation, badge name extraction, full page extraction (Spanish/English differentiation, responsive deduplication, validation logging)
- All CodeQL alerts (#49-52) resolved

## Prevention

- **Prefer canonical identifiers over derived ones.** Badge filenames, display names, and image alt-text are presentation artifacts -- they can be identical across distinct entities. Page URLs and href links are canonical identifiers maintained by the platform.
- **Validate URL domains with urlparse, not substring checks.** `'domain.com' in url` matches `evildomain.com`. Use `urlparse(url).netloc == 'domain.com'` instead.
- **Handle both absolute and relative URLs.** Selenium page_source has relative hrefs (`/garfield`), while saved HTML has absolute URLs. Slug extraction must handle both.
- **When fixing extraction logic, clean historical data.** Old data files with wrong slugs will persist through merge-based feed regeneration. Either clean the files or revert feeds to a known-good state before rebuilding.
- **Understand merge vs overwrite in feed generation.** The `regenerate_feed` function merges with existing feed files, preserving contaminated entries. When data is known-bad, start from clean feeds.

## Key Insight

When scraping structured pages, extract identifiers from the **canonical link** within each item's container, not from derived attributes like image filenames or display names. The link is the platform's own identifier and is guaranteed to be unique and correct. This is the same pattern used successfully by the Comics Kingdom scraper.

## Related Documentation

- `docs/solutions/ui-bugs/spanish-ui-filter-missing-comics-source-list-mismatch.md` -- related Spanish comics catalog issue (different root cause)
- `docs/plans/2026-03-31-001-fix-gocomics-feed-generation-plan.md` -- plan for the data-driven feed generation overhaul
- Git commits: `669779ac8` (scraper fix), `653272946` (CodeQL fix), `817400f16` (feed revert and backfill)
