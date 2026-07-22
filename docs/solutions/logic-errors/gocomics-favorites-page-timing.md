---
title: "GoComics favorites page is reactive: scraping at 03:20 CT misses late-publishing political cartoonists"
date: 2026-05-16
category: logic-errors
tags: [scraping, gocomics, timing, political-cartoons, favorites-page, page-state, backfill]
stack: [python, selenium, beautifulsoup]
github_issues: [138, 164]
---

## Problem

GitHub #138 reported Nick Anderson missing from his GoComics political feed despite still publishing daily on the site. Investigation revealed that 10+ political cartoonists configured on the user's GoComics favorites page (`https://www.gocomics.com/profile/User52732/comics/221821`) were systematically missing from our daily scrape data — Nick Anderson appeared in only 3 of 136 daily scrape JSONs since January.

The favorites page consistently reported 61 total comics (`updated + not_updated`). The user confirmed Nick Anderson, Rob Rogers, and others were on his favorites page. The scrape data did not reflect them.

## Investigation

A targeted diagnostic script (`scripts/diagnose_political_favorites.py`) fetched the political favorites page directly with `?date=2026-05-14`, ~48 hours after the production scrape ran for that date. Results:

| Run | Time | ComicViewer (updated) | FeaturesNotIssued | Total |
|-----|------|----------------------:|------------------:|------:|
| Production scrape | 03:20 CT, May 14 | 10 | 51 | 61 |
| Diagnostic fetch | ~14:00 CT, May 16 (querying `?date=2026-05-14`) | **21** | 40 | 61 |

Production's 10 extracted slugs were a strict subset of the diagnostic's 21. The 11 additional slugs included `nickanderson` and 10 other political cartoonists with chronically-stale feeds:

`bill-bramhall`, `chrisbritt`, `drewsheneman`, `jeffstahler`, `joelpett`, `joey-weatherford`, `kal`, `lisabenson`, `mattdavies`, `nickanderson`, `robrogers`

When the production scraper's extraction code is re-run against the diagnostic's saved HTML, it cleanly extracts all 21 unique slugs. So the extractor is fine — the bug is in **when** the page is fetched, not how it's parsed.

## Root cause

The GoComics favorites page renders as-of-now: a comic is classified into `ComicViewer` (published) vs `FeaturesNotIssued` (not yet published / won't publish today) based on the page's view of the world at request time. The `?date=` query parameter selects which day's strips to show, but the published-vs-not classification remains a function of "what has actually been posted by the time of the HTTP request."

Most editorial cartoonists publish mid-morning Eastern (roughly 09:00–13:00 ET). At 03:20 CT (04:20 ET), only a small subset of strips for the day have been syndicated. The page lists the rest as `FeaturesNotIssued`. By the time we re-fetch the same `?date=` URL many hours later, those late-publishing strips have appeared and moved to `ComicViewer` — but our daily scrape never sees that second state because we only fetch once per day, early in the morning Central.

Comics whose syndication runs after our 03:20 CT window were therefore never appearing in scrape data, regardless of how reliably they posted.

## Fix

> **Timezone note:** the automation host runs on **US Central time** (logs print
> `CDT`/`CST`). Earlier revisions of this doc labeled times "PT" inconsistently —
> some values were Central clock readings, and one ("13:00 PT") was self-
> contradictory against its own "14:00 ET" rationale. All times here are now stated
> in **Central (CT)** with the Eastern equivalent where it matters, matching the
> launchd schedule (`master` = Hour 3, `pass2` = Hour 13). Note 13:00 CT = 14:00 ET.

Two-pass GoComics scrape:
- **Pass 1 — 03:20 CT (unchanged):** captures overnight-syndicated content.
- **Pass 2 — 13:00 CT / 14:00 ET (new):** re-fetches the GoComics favorites pages and merges new slugs into the same-day `data/comics_$DATE.json`. Pass 2 entries win for slugs present in both passes; pass 1's slugs not seen in pass 2 are preserved.

Pass 2 is GoComics-only — the other five sources (Comics Kingdom, TinyView, Far Side, New Yorker, Creators) don't use a single reactive favorites page, so their existing timing is fine.

13:00 CT (14:00 ET) was chosen as a balance: late enough that the mid-morning Eastern publishing wave has finished (14:00 ET), early enough that feeds refresh well before evening RSS consumption. The two-pass design is self-tuning — once we have a few weeks of pass-2 data, the gap between pass 1 and pass 2 captures tells us whether to shift pass 2 earlier or later.

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

## Update — issue #164: the late/next-day tail beyond Pass 2

GitHub #164 reported Jack Ohman's feed stale since 2026-07-02. Same class of bug as
#138, but one the two-pass fix above does **not** catch: cartoonists who publish
*after* the 13:00 CT Pass 2 window, or on a next-day lag.

**Evidence (2026-07-10, via `scripts/diagnose_political_favorites.py`):** re-fetching the
political page with `?date=2026-07-08` showed `jackohman` in the `ComicViewer` (updated)
set, and replaying the production extractor against that saved HTML pulled him out cleanly
(valid strip image) — so it is a timing gap, not an extraction bug. Cross-checking the
settled Jul-8 "updated" set against `data/comics_2026-07-08.json` found **11 of 25**
political comics that published Jul 8 were missed by both passes: `bill-bramhall`,
`chrisbritt`, `garymarkstein`, `garyvarvel`, `henrypayne`, `jackohman`, `jeffstahler`,
`joe-heller`, `kal`, `mattdavies`, `pedroxmolina`. Jack Ohman had been captured only ~7
days since April — the same systemic tail, not an Ohman-specific problem. A slug missed on
its publish date is never written to any dated JSON, so the miss was permanent.

**Fix — rolling backfill (issue #164).** The favorites page is reactive in our favour too:
re-fetching `?date=<past-date>` returns that day's *settled* updated/not-issued state once
the strip exists. So each daily run now re-scrapes the political favorites page for the last
`GOCOMICS_BACKFILL_DAYS` days (default 3) and merges any newly-appeared slugs into that day's
`data/comics_<date>.json`:

- `scripts/authenticated_scraper_secure.py` gained `page_url_for_date()`, `backfill_target_dates()`,
  `run_backfill()`, and a `--backfill-days N` flag. After the same-day scrape it re-fetches the
  political page(s) for each past date (one login) and merges via the existing
  `merge_with_existing` (additive for new slugs, replacive for overlapping same-date ones).
- `scripts/local_pass2_update.sh` runs it (`--backfill-days "$BACKFILL_DAYS"`) and — the
  load-bearing part — stages **every** date file the run touched (today plus the backfill
  window) on both the happy-path commit and the push-conflict recovery. Previously all three
  staging points hardcoded today's file, so backfilled past-date JSON would regenerate into
  feeds but never commit, then be wiped by the next run's `git reset --hard origin/main`. The
  touched-date set is an explicit enumerated list, never a `data/comics_*.json` glob.

**Why 3 days is robust despite next-day/late posting:** each past date is re-fetched on every
subsequent in-window day (enters as `today-1`, re-scraped as `today-2`, `today-3`), so
within-window late settling is self-healing. Only lateness *exceeding* the window is missed;
`GOCOMICS_BACKFILL_DAYS` widens it without code edits. Recovering a gap *older* than the
window (e.g. #164's Jul 2–7 backlog) is a one-off wider `--backfill-days` run.

## Related

- Issue #138 (Nick Anderson missing from GoComics feed)
- Issue #164 (Jack Ohman feed not updating — the late/next-day tail)
- Plan: `docs/plans/2026-07-10-001-fix-gocomics-late-publisher-backfill-plan.md`
- `scripts/authenticated_scraper_secure.py` — the production GoComics scraper + rolling backfill
- `scripts/local_pass2_update.sh` — Pass 2, which runs the backfill and stages all touched dates
- `docs/solutions/logic-errors/gocomics-spanish-english-feed-contamination.md` — prior GoComics scrape-correctness work
