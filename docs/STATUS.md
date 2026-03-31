# Project Status
<!-- Updated: 2026-03-31 by Adam -->

## Project Overview
ComicCaster is a hybrid Python + Netlify application that aggregates comics from GoComics, Comics Kingdom, TinyView, and The Far Side, then generates standards-compliant RSS feeds and OPML bundles so readers can subscribe in any feed reader.


## Current State
Project is stable. GoComics feed generation was overhauled to use data-driven approach. All security alerts resolved.

**Phase:** Maintenance (active)
**Last Session:** 2026-03-31
**Last Session Summary:** Fixed GoComics feed generation failure, resolved security alerts, added SECURITY.md, updated CI matrix.

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- GoComics feeds generated from Phase 1 scraped data (no per-comic HTTP requests)
- Manual backfill script available for feed recovery (`scripts/backfill_gocomics_feeds.py`)
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled

## What's In Progress
<!-- Active work items. Update every session. -->

| Item | Status | Branch | Notes |
|------|--------|--------|-------|
| No active work | Complete | main | All items from 2026-03-31 session merged |

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. Monitor tonight's 3 AM automated run to confirm GoComics fix works in production
2. Clean up stale git stashes (18 accumulated)
3. Continue monitoring automated feed updates for breakages

## Open Decisions
<!-- Architectural or product decisions that haven't been made yet. -->
<!-- These are the most expensive things to lose between sessions. -->

| Decision | Options Considered | Leaning Toward | Blocking? |
|----------|--------------------|----------------|-----------|
|          |                    |                |           |

## Known Issues
<!-- Bugs, tech debt, or things that are broken but not urgent. -->

- 314 of 467 GoComics comics are not in Phase 1 scraped data (not captured by bulk scrape profiles). These comics don't get daily updates. May need to expand Phase 1 profile coverage.

## Environment & Setup
<!-- How to run this project. Critical for fresh agent sessions. -->

**Run locally:** `netlify dev` (full stack at `http://localhost:8888`) or `python run_app.py` (Flask at `http://localhost:5001`)
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) -- 181 tests, requires Python >=3.10
**Deploy:** Push to `main` to trigger Netlify deployment
**Key env vars:** `FLASK_DEBUG` (local optional), `NODE_VERSION`, `NETLIFY_FUNCTIONS_DIR`

## Architecture Notes
Hybrid architecture: Python package (`comiccaster/`) handles scraping and feed generation, Netlify static hosting serves `public/`, and serverless functions in `functions/` support OPML generation and feed preview.

GoComics feed generation follows the same data-driven pattern as Comics Kingdom and TinyView: Phase 1 collects data to `data/comics_YYYY-MM-DD.json`, then `scripts/generate_gocomics_feeds.py` reads that data and generates feeds. A separate `scripts/backfill_gocomics_feeds.py` exists for manual recovery.


## Session Log
<!-- Brief log of recent sessions. Newest first. Delete entries older than 30 days. -->

### 2026-03-31
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
- **Discovered:** 314/467 GoComics comics aren't in Phase 1 data -- may need to expand scrape profile coverage

### 2026-02-23
- **Goal:** Initialize compound engineering docs structure
- **Accomplished:** Created docs/ directory with STATUS.md, plans/, solutions/, decisions/, brainstorms/
- **Didn't finish:** Fill in deeper project details and backlog priorities
- **Discovered:** Project is currently in maintenance/on-hold mode with no recent active development
