# Project Status
<!-- Updated: 2026-04-02 by Adam -->

## Project Overview
ComicCaster is a hybrid Python + Netlify application that aggregates comics from GoComics, Comics Kingdom, TinyView, and The Far Side, then generates standards-compliant RSS feeds and OPML bundles so readers can subscribe in any feed reader.


## Current State
Project is stable. Standardized comic strip sizing/alignment in RSS feeds (#105). Cleaned up stale remote branches. Claude Code agent orchestration workflow (red-orchestrator + claude bot) tested successfully for the first time.

**Phase:** Maintenance (active)
**Last Session:** 2026-04-02
**Last Session Summary:** Reviewed and merged Claude Code's fix for inconsistent comic strip sizing/alignment (#105). Cleaned up 2 stale remote branches. 209 tests passing.

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- GoComics scraper extracts 257 comics from profile pages using href-based slug extraction (correctly separates Spanish/English versions)
- GoComics feeds generated from Phase 1 scraped data (no per-comic HTTP requests)
- 312 GoComics feeds updating daily (up from 115 before scraper fix)
- Manual backfill script available for feed recovery (`scripts/backfill_gocomics_feeds.py`)
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled
- All CodeQL security alerts resolved (proper URL domain validation)
- Consistent comic strip sizing (max-width: 700px) and centering across all sources (#105)

## What's In Progress
<!-- Active work items. Update every session. -->

| Item | Status | Branch | Notes |
|------|--------|--------|-------|
| No active work | Complete | main | All items from 2026-03-31 evening session merged |

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. Clean up stale git stashes (18 accumulated)
2. Continue monitoring automated feed updates for breakages
3. Address remaining ~155 GoComics comics not on profile pages

## Open Decisions
<!-- Architectural or product decisions that haven't been made yet. -->
<!-- These are the most expensive things to lose between sessions. -->

| Decision | Options Considered | Leaning Toward | Blocking? |
|----------|--------------------|----------------|-----------|
|          |                    |                |           |

## Known Issues
<!-- Bugs, tech debt, or things that are broken but not urgent. -->

- ~155 of 467 GoComics catalog comics are not captured by the profile page scraper (comics not on any of the 6 profile pages). These comics don't get daily updates via the new pipeline. The backfill script can recover them individually.
- Old data files (pre-March 31) have been cleaned but contain fewer entries (~100/day vs 257) since only ~115 comics had matching slugs under the old badge-based extraction.

## Environment & Setup
<!-- How to run this project. Critical for fresh agent sessions. -->

**Run locally:** `netlify dev` (full stack at `http://localhost:8888`) or `python run_app.py` (Flask at `http://localhost:5001`)
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) -- 209 tests, requires Python >=3.10
**Deploy:** Push to `main` to trigger Netlify deployment
**Key env vars:** `FLASK_DEBUG` (local optional), `NODE_VERSION`, `NETLIFY_FUNCTIONS_DIR`

## Architecture Notes
Hybrid architecture: Python package (`comiccaster/`) handles scraping and feed generation, Netlify static hosting serves `public/`, and serverless functions in `functions/` support OPML generation and feed preview.

GoComics feed generation follows the same data-driven pattern as Comics Kingdom and TinyView: Phase 1 collects data to `data/comics_YYYY-MM-DD.json`, then `scripts/generate_gocomics_feeds.py` reads that data and generates feeds. A separate `scripts/backfill_gocomics_feeds.py` exists for manual recovery.


## Session Log
<!-- Brief log of recent sessions. Newest first. Delete entries older than 30 days. -->

### 2026-04-02
- **Goal:** Review and merge Claude Code's fix for comic strip sizing/alignment (#105), clean up remote branches
- **Accomplished:**
  - Reviewed issue #105 (user-reported inconsistent strip sizing and alignment in RSS readers)
  - Reviewed Claude Code's fix on `claude/issue-105-20260402-2158` -- wraps all comic images in centering div with max-width: 700px in `feed_generator.py`, adds 2 new tests
  - All 209 tests passing; merged into main
  - Deleted stale remote branches: `fix/gocomics-feed-generation` (already merged), `feature/v1.1-political-comics-epic-2` (work already in main via other PRs)
  - First successful use of red-orchestrator + Claude Code agent orchestration workflow
- **Didn't finish:** Nothing left outstanding
- **Discovered:** Agent orchestration (red-orchestrator dispatching to Claude Code) works end-to-end for straightforward fixes

### 2026-03-31 (evening)
- **Goal:** Fix Spanish strips appearing in English feeds (#103), fix FoxTrot contamination (#104), resolve CodeQL alerts
- **Accomplished:**
  - Rewrote `extract_comics_from_page` in `authenticated_scraper_secure.py` to use href-based slug extraction from comic containers (was badge filename-based, causing slug mismatches and Spanish/English conflation)
  - Added `_extract_comic_slug_from_link`, `_is_asset_host`, `_get_image_src`, `_get_badge_name` helpers
  - Added slug+date deduplication in `generate_gocomics_feeds.py`
  - Added page-level validation logging (cross-checks extraction against page metadata)
  - Created `tests/test_authenticated_scraper.py` (24 tests) -- total test suite now 40 tests
  - Fixed CodeQL alerts #49-52 (replaced URL substring checks with `urlparse().netloc` domain validation)
  - Cleaned 5,230 contaminated entries from old data files
  - Reverted all GoComics feeds to March 30 (pre-contamination) and backfilled 2 days (306 feeds updated, 0 failures)
  - Sanitized code comments to avoid revealing page structure details
  - Feed coverage jumped from 115 to 312 GoComics feeds updating daily
- **Didn't finish:** Nothing left outstanding
- **Discovered:** `regenerate_feed` in `update_feeds.py` merges with existing feed data, which can preserve contamination; backfill approach requires clean base feeds

### 2026-03-31 (morning)
- **Goal:** Fix GoComics feed generation failure (zero feeds updated despite "ALL SUCCESS" report)
- **Accomplished:**
  - Created `scripts/generate_gocomics_feeds.py` -- data-driven daily feed generator (PR #102)
  - Created `scripts/backfill_gocomics_feeds.py` -- manual rate-limited recovery script
  - Fixed misleading success reporting in `process_comic()` / `main()`
  - Updated `local_master_update.sh` to use new generator
  - Bumped `requests` to 2.33.1 (Dependabot security fix)
  - Fixed CodeQL alert #48 (incomplete URL substring sanitization in `public/index.html`)
  - Added SECURITY.md with GitHub private vulnerability reporting
  - Dropped EOL Python 3.9 from CI, added 3.12
  - Merged Dependabot PR #100 (pytz 2024.1 -> 2026.1.post1)
- **Didn't finish:** Nothing left outstanding
- **Discovered:** Badge-based slug extraction was root cause of both Spanish contamination and 142 dropped comics

### 2026-02-23
- **Goal:** Initialize compound engineering docs structure
- **Accomplished:** Created docs/ directory with STATUS.md, plans/, solutions/, decisions/, brainstorms/
- **Didn't finish:** Fill in deeper project details and backlog priorities
- **Discovered:** Project is currently in maintenance/on-hold mode with no recent active development
