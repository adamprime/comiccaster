---
title: "GoComics favorites page is reactive: scraping at 03:20 PT misses late-publishing political cartoonists"
date: 2026-05-16
category: logic-errors
tags: [scraping, gocomics, timing, political-cartoons, favorites-page, page-state]
stack: [python, selenium, beautifulsoup]
github_issues: [138]
---

## Problem

GitHub #138 reported Nick Anderson missing from his GoComics political feed despite still publishing daily on the site. Investigation revealed that 10+ political cartoonists configured on the user's GoComics favorites page (`https://www.gocomics.com/profile/User52732/comics/221821`) were systematically missing from our daily scrape data — Nick Anderson appeared in only 3 of 136 daily scrape JSONs since January.

The favorites page consistently reported 61 total comics (`updated + not_updated`). The user confirmed Nick Anderson, Rob Rogers, and others were on his favorites page. The scrape data did not reflect them.

## Investigation

A targeted diagnostic script (`scripts/diagnose_political_favorites.py`) fetched the political favorites page directly with `?date=2026-05-14`, ~48 hours after the production scrape ran for that date. Results:

| Run | Time | ComicViewer (updated) | FeaturesNotIssued | Total |
|-----|------|----------------------:|------------------:|------:|
| Production scrape | 03:20 PT, May 14 | 10 | 51 | 61 |
| Diagnostic fetch | ~14:00 PT, May 16 (querying `?date=2026-05-14`) | **21** | 40 | 61 |

Production's 10 extracted slugs were a strict subset of the diagnostic's 21. The 11 additional slugs included `nickanderson` and 10 other political cartoonists with chronically-stale feeds:

`bill-bramhall`, `chrisbritt`, `drewsheneman`, `jeffstahler`, `joelpett`, `joey-weatherford`, `kal`, `lisabenson`, `mattdavies`, `nickanderson`, `robrogers`

When the production scraper's extraction code is re-run against the diagnostic's saved HTML, it cleanly extracts all 21 unique slugs. So the extractor is fine — the bug is in **when** the page is fetched, not how it's parsed.

## Root cause

The GoComics favorites page renders as-of-now: a comic is classified into `ComicViewer` (published) vs `FeaturesNotIssued` (not yet published / won't publish today) based on the page's view of the world at request time. The `?date=` query parameter selects which day's strips to show, but the published-vs-not classification remains a function of "what has actually been posted by the time of the HTTP request."

Most editorial cartoonists publish mid-morning Eastern (roughly 09:00–13:00 ET). At 03:20 PT (06:20 ET), only a small subset of strips for the day have been syndicated. The page lists the rest as `FeaturesNotIssued`. By the time we re-fetch the same `?date=` URL many hours later, those late-publishing strips have appeared and moved to `ComicViewer` — but our daily scrape never sees that second state because we only fetch once per day, early in the morning Pacific.

Comics whose syndication runs after our 03:20 PT window were therefore never appearing in scrape data, regardless of how reliably they posted.

## Fix

Two-pass GoComics scrape:
- **Pass 1 — 03:20 PT (unchanged):** captures overnight-syndicated content.
- **Pass 2 — 11:00 PT (new):** re-fetches the GoComics favorites pages and merges new slugs into the same-day `data/comics_$DATE.json`. Pass 2 entries win for slugs present in both passes; pass 1's slugs not seen in pass 2 are preserved.

Pass 2 is GoComics-only — the other five sources (Comics Kingdom, TinyView, Far Side, New Yorker, Creators) don't use a single reactive favorites page, so their existing timing is fine.

11:00 PT was chosen as a balance: late enough that the mid-morning Eastern publishing wave has finished (14:00 ET), early enough that feeds refresh well before evening RSS consumption. The two-pass design is self-tuning — once we have a few weeks of pass-2 data, the gap between pass 1 and pass 2 captures tells us whether to shift pass 2 earlier or later.

## Diagnostic tooling

`scripts/diagnose_political_favorites.py` is preserved for future investigation of similar discrepancies. It runs the same OAuth + Chrome flow as the production scraper, fetches the political favorites page for a specified date, saves the rendered HTML, and reports both `ComicViewer` and `FeaturesNotIssued` slug sets — flagging a target slug's presence or absence. Run:

```bash
python scripts/diagnose_political_favorites.py --date YYYY-MM-DD --target-slug <slug>
```

## What this rules out

- **Slug rename / redirect** — `nickanderson` is the current canonical slug on GoComics' political-a-to-z directory and on the user's favorites page. No rename happened.
- **Authentication / session issue** — same auth flow works for the diagnostic and the production scraper.
- **Extraction bug** — replaying the production extractor against the diagnostic HTML extracts all 21 slugs successfully.
- **Pagination / lazy-load** — only 21 of 63 ComicViewer containers extract cleanly, but the other 42 are responsive-layout duplicates; deduplication is working correctly.

## Related

- Issue #138 (Nick Anderson missing from GoComics feed)
- `scripts/authenticated_scraper_secure.py` — the production GoComics scraper
- `docs/solutions/logic-errors/gocomics-spanish-english-feed-contamination.md` — prior GoComics scrape-correctness work
