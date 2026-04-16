---
title: "feat: Extend feed history to 90 days"
type: feat
status: active
date: 2026-04-15
---

# feat: Extend feed history to 90 days

## Overview

Extend RSS feed history from ~10 days to 90 days so subscribers can scroll back further in their feed readers. Requested by a user in issue #113.

## Problem Frame

Feeds currently contain ~10 days of history because the feed generation scripts only load 10 days of scraped data files when rebuilding. The data files themselves go back 141+ days (GoComics) and 151+ days (Comics Kingdom, TinyView), so the raw data already exists — it's just not being loaded into the feeds.

## Requirements Trace

- R1. GoComics, Comics Kingdom, and TinyView feeds should contain up to 90 days of history
- R2. Far Side feeds are unaffected (they use live scraping with their own retention logic)
- R3. No increase in external HTTP requests (all data is read from local JSON files)
- R4. Existing feed URLs and format remain unchanged
- R5. TinyView scraper should fetch 90 days of history to match

## Scope Boundaries

- Far Side feeds are out of scope — they use live scraping and ID-based tracking, not data files
- The legacy `update_feeds.py` scraping path is out of scope — it's not used in daily automation
- Data file cleanup/rotation is out of scope — files are small and accumulate indefinitely with no issues
- Backfill of existing feeds is not needed — history will build up naturally over daily runs as the merge logic preserves existing entries

## Context & Research

### Relevant Code and Patterns

All three data-driven feed generators follow the same pattern:
1. Load N days of scraped JSON data files from `data/`
2. Group entries by comic slug, deduplicate
3. Merge new entries into existing feed XML (preserving old entries)
4. Write updated feed XML

The merge-and-preserve behavior means feeds will accumulate 90 days of history over time without needing a backfill.

### Retention settings by source

| Source | Script | Current `days_back` | Entry limit | Change needed |
|--------|--------|---|---|---|
| GoComics | `scripts/generate_gocomics_feeds.py:34` | 10 | None | Yes → 90 |
| Comics Kingdom | `scripts/generate_comicskingdom_feeds.py:106` | 10 | None | Yes → 90 |
| TinyView generator | `scripts/generate_tinyview_feeds_from_data.py` | All files | None | No change needed |
| TinyView scraper | `scripts/tinyview_scraper_local_authenticated.py:231` | 15 | None | Yes → 90 |
| TinyView scraper (lib) | `comiccaster/tinyview_scraper.py` default | 15 | None | Yes → 90 |
| Far Side | `scripts/update_farside_feeds.py` | 3 (daily dose) | None | No (out of scope) |
| Legacy path | `scripts/update_feeds.py:545` | 10 | 100 | No (not used daily) |
| Backfill | `scripts/backfill_gocomics_feeds.py` | 10 (CLI arg) | 100 (via legacy) | No (manual tool) |
| Master script | `scripts/local_master_update.sh:89` | 15 (TinyView) | N/A | Yes → 90 |

## Key Technical Decisions

- **90 days, not 60:** The user asked for 60-90. Going to 90 costs nothing extra (local file reads) and gives the most value. Daily comics = 90 entries, well within reasonable RSS feed size.
- **No entry count cap change needed:** The `max_feed_entries=100` in `update_feeds.py` only applies to the legacy scraping path, which is not part of the daily automation. The current generators have no cap, which is fine — 90 daily entries per feed is small.
- **No backfill needed:** The merge logic preserves existing entries when regenerating. Feeds will naturally accumulate to 90 days over the next ~80 daily runs. This is acceptable — the user didn't ask for immediate 90-day backfill.

## Implementation Units

- [ ] **Unit 1: Bump days_back in feed generators and scraper**

  **Goal:** Change the data loading window from 10/15 days to 90 days across all affected scripts.

  **Requirements:** R1, R3, R5

  **Dependencies:** None

  **Files:**
  - Modify: `scripts/generate_gocomics_feeds.py` (line 34, `days_back` default 10 → 90)
  - Modify: `scripts/generate_comicskingdom_feeds.py` (line 106, `days_back` default 10 → 90)
  - Modify: `scripts/tinyview_scraper_local_authenticated.py` (line 231, `--days-back` default 15 → 90)
  - Modify: `comiccaster/tinyview_scraper.py` (`days_back` default parameter → 90)
  - Modify: `scripts/local_master_update.sh` (line 89, `--days-back 15` → `--days-back 90`)

  **Approach:**
  - Each change is a single integer default value change
  - TinyView scraper fetches live pages, so 90 days means more HTTP requests on scrape runs — but this is paced and runs once daily, so the impact is minimal
  - TinyView generator already loads all files, so no change needed there

  **Patterns to follow:**
  - Existing parameter defaults in each script

  **Test scenarios:**
  - Existing tests for `load_scraped_data()` in `tests/test_generate_gocomics_feeds.py` should still pass (they supply explicit `days_back` values)
  - Existing Comics Kingdom tests should still pass
  - Verify no test hardcodes the old default and asserts on it

  **Verification:**
  - `pytest -v` passes with no regressions
  - Running `generate_gocomics_feeds.py` locally loads >10 days of data (visible in log output)

- [ ] **Unit 2: Comment on issue #113**

  **Goal:** Respond to the user's feature request with what was done.

  **Requirements:** R1

  **Dependencies:** Unit 1

  **Approach:**
  - Thank the user for the suggestion
  - Explain that feed history has been extended to 90 days
  - Note that history will build up gradually over daily runs (not instant backfill)
  - Close the issue

## Risks & Dependencies

- **TinyView scraper pacing:** Increasing from 15 to 90 days of live scraping could be slower. The scraper already has pacing built in, so this should be fine but worth monitoring the first run.
- **Feed file size:** 90 entries per feed × 648 feeds = modest increase. Average feed will grow from ~10KB to ~50-60KB over time. Total repo size impact is manageable.

## Sources & References

- Related issue: #113
- Prior art: `scripts/generate_gocomics_feeds.py` created in commit 0855ed7 (2026-03-31) with `days_back=10` as a conservative default when migrating from per-comic fetching to data-driven generation
