# Project Status
<!-- Updated: 2026-04-09 by Adam -->

## Project Overview
ComicCaster is a hybrid Python + Netlify application that aggregates comics from GoComics, Comics Kingdom, TinyView, and The Far Side, then generates standards-compliant RSS feeds and OPML bundles so readers can subscribe in any feed reader.


## Current State
Project is stable overall, but Comics Kingdom automation had a transient failure on 2026-04-16 that required manual recovery. Root cause was not the 90/100-day feed-history expansion; the CK scraper initially failed after a Chrome / automation environment problem and stale live browser auth, but manual reauth plus a visible-browser rerun succeeded.

**Phase:** Maintenance (active)
**Last Session:** 2026-04-16
**Last Session Summary:** Recovered same-day Comics Kingdom scrape/feed generation after morning partial failure; confirmed CK raw JSON should remain git-tracked like GoComics and TinyView, and fixed an incorrect `.gitignore` rule introduced during Apr 9 cleanup.

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- Daily automated feed monitoring via agent
- GoComics scraper extracts 257 comics from profile pages using href-based slug extraction (correctly separates Spanish/English versions)
- GoComics feeds generated from Phase 1 scraped data (no per-comic HTTP requests)
- 312 GoComics feeds updating daily (up from 115 before scraper fix)
- Manual backfill script available for feed recovery (`scripts/backfill_gocomics_feeds.py`)
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled
- All CodeQL security alerts resolved (proper URL domain validation)
- Consistent comic strip sizing (max-width: 700px) and centering across all sources (#105)
- Comics Kingdom scraper adapted to current site structure (data-attribute-based extraction, lazy image handling)

## What's In Progress
<!-- Active work items. Update every session. -->

| Item | Status | Branch | Notes |
|------|--------|--------|-------|
| CK automation stability | Monitoring | main | 2026-04-16 manual run succeeded after reboot + reauth; need to watch next scheduled run to confirm unattended stability |

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. Investigate issue #91 (GoComics strips don't save to read-later platforms)

## Open Decisions
<!-- Architectural or product decisions that haven't been made yet. -->
<!-- These are the most expensive things to lose between sessions. -->

| Decision | Options Considered | Leaning Toward | Blocking? |
|----------|--------------------|----------------|-----------|
|          |                    |                |           |

## Known Issues
<!-- Bugs, tech debt, or things that are broken but not urgent. -->

- GoComics strips don't save to read-later platforms like Pocket/Instapaper (#91) -- approach TBD
- Old data files (pre-March 31) have been cleaned but contain fewer entries (~100/day vs 257) since only ~115 comics had matching slugs under the old badge-based extraction.
- CK unattended browser automation needs monitoring after 2026-04-16. Morning run failed during CK scraping even though manual visible-browser rerun succeeded after reboot + reauth.

## Environment & Setup
<!-- How to run this project. Critical for fresh agent sessions. -->

**Run locally:** `netlify dev` (full stack at `http://localhost:8888`) or `python run_app.py` (Flask at `http://localhost:5001`)
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) -- 212 tests, requires Python >=3.10
**Deploy:** Push to `main` to trigger Netlify deployment
**Key env vars:** `FLASK_DEBUG` (local optional), `NODE_VERSION`, `NETLIFY_FUNCTIONS_DIR`

## Architecture Notes
Hybrid architecture: Python package (`comiccaster/`) handles scraping and feed generation, Netlify static hosting serves `public/`, and serverless functions in `functions/` support OPML generation and feed preview.

GoComics feed generation follows the same data-driven pattern as Comics Kingdom and TinyView: Phase 1 collects data to `data/comics_YYYY-MM-DD.json`, then `scripts/generate_gocomics_feeds.py` reads that data and generates feeds. A separate `scripts/backfill_gocomics_feeds.py` exists for manual recovery.

**Important data-tracking note (confirmed 2026-04-16):** raw source JSON files are part of the intended architecture for all major sources, not ephemeral diagnostics:
- GoComics → `data/comics_YYYY-MM-DD.json` (git tracked)
- TinyView → `data/tinyview_YYYY-MM-DD.json` (git tracked)
- Comics Kingdom → `data/comicskingdom_YYYY-MM-DD.json` (should be git tracked)

An Apr 9 `.gitignore` cleanup accidentally added `data/comicskingdom_*.json` under "Diagnostics and ephemeral data," which conflicted with:
- existing tracked CK history
- feed generation behavior (`generate_comicskingdom_feeds.py` loads multiple day files)
- local automation docs / GitHub Actions assumptions

This was corrected on 2026-04-16. Do **not** treat CK daily JSON as disposable scratch data.


## Session Log
<!-- Brief log of recent sessions. Newest first. Delete entries older than 30 days. -->

### 2026-04-16
- **Goal:** Recover same-day Comics Kingdom freshness after morning partial failure and understand repo/data-model implications before committing anything
- **Accomplished:**
  - Investigated morning master update failure and confirmed CK scrape failed while downstream feed generation still succeeded from previously tracked raw JSON
  - Diagnosed first failure as Chrome / ChromeDriver mismatch warning, then discovered manual visible-browser rerun worked after reboot + reauth
  - Manually reran `scripts/comicskingdom_scraper_individual.py` successfully for all 153 comics and regenerated CK feeds
  - Confirmed CK feed XML files were actually updated before commit
  - Researched repo structure before committing: verified GoComics, TinyView, and historical CK raw JSON are all git-tracked and are part of the feed-generation architecture
  - Traced contradictory `.gitignore` rule to Apr 9 cleanup commit `dc6cb2a3041ecca9efefedcb61a31d0ad1944178`, where CK JSON was mistakenly reclassified as ephemeral diagnostics
  - Pushed recovery commit `6b8ff12fc` (manual CK scrape recovery) and follow-up commit `f1d7a0680` (remove incorrect CK JSON ignore rule)
- **Didn't finish:** Root-cause unattended CK browser instability remains only partially understood; next scheduled run should be watched closely
- **Discovered:** The 90/100-day feed-history expansion was not the cause of the morning failure. CK raw JSON is durable pipeline input, not throwaway diagnostics. Manual reauth in a live browser session can restore CK scraping when unattended automation wedges.

### 2026-04-09 (evening)
- **Goal:** Housekeeping and dependency updates
- **Accomplished:**
  - Cleared all 19 stale git stashes (all superseded by current main)
  - Cleaned up .gitignore: removed .coverage from tracking, added patterns for cookie files in data/, diagnostics, backup feeds, test preview dir
  - Committed docs scaffolding .gitkeep files (brainstorms, decisions, plans, solutions)
  - Reviewed and merged 3 Dependabot PRs: pytest 8.4.2->9.0.2, python-dotenv 1.2.1->1.2.2, selenium 4.36.0->4.41.0
  - Corrected STATUS.md: removed inaccurate "~155 missing GoComics" item (not all comics post daily), noted feed monitoring is handled by agent
- **Didn't finish:** Nothing left outstanding
- **Discovered:** The ~155 "missing" GoComics comics were not actually missing -- many comics simply don't post every day

### 2026-04-09
- **Goal:** Fix Comics Kingdom scraper breakage (upstream site redesign)
- **Accomplished:**
  - Diagnosed CK extraction failure: upstream redesigned their favorites page (new component structure, image proxy, paginated loading)
  - Rewrote extraction to use structured data attributes instead of generic element traversal
  - Added paginated content loading (click-to-expand) to capture full favorites list
  - Fixed lazy image loading by forcing eager load via JS before parsing
  - Handled slug normalization for vintage comics to match existing catalog
  - Added diagnostic snapshot on zero-extraction failures (screenshot + HTML)
  - Added popup/interstitial dismissal
  - Created `scripts/diagnose_ck_page.py` diagnostic tool
  - 102 comics extracted successfully (was 0), 144 images loaded, all slugs match catalog
  - 212 tests passing, no regressions
- **Didn't finish:** Nothing left outstanding
- **Discovered:** CK now uses a vertical reader layout with paginated loading instead of a grid; images are proxied through a CDN layer; structured data attributes on reader items are more reliable than element traversal

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
