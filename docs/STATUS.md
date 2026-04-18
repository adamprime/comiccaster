# Project Status
<!-- Updated: 2026-04-18 by Adam -->

## Project Overview
ComicCaster aggregates comics from GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, and Creators Syndicate into standards-compliant RSS feeds and OPML bundles. A Python pipeline handles scraping and feed generation; Netlify serves the static site and feed files.

## Current State
Stable, with Shape A live on `main`. Today's reliability pass diagnosed the chronic CK renderer-timeout failure as a WAF slow-walk on `driver.get("https://comicskingdom.com")` (the navigation that precedes cookie injection), and replaced the pickled-cookie flow with a persistent Chrome profile at `~/.comicskingdom_chrome_profile`. End-to-end validation at 16:12 confirmed the fix: Chrome startup + auth check went from ~23–33s (with frequent timeouts) to ~5s, with the `load_cookies: driver.get(...)` code path never invoked under profile mode. Tonight's 3 AM LaunchD run is the final unattended validation.

**Phase:** Maintenance (active)
**Last Session:** 2026-04-18
**Last Session Summary:** Troubleshot this morning's CK failure → diagnosed + fixed the chronic renderer-timeout root cause → cleared three Known Issues items along the way. Shipped four PRs: #114 (instrumentation + smoke tests), #115 (diagnosis findings + `_secure` instrumentation), #116 (unrelated testenv cleanup: bin gitignore, webdriver-manager dep, two test side-effect writes), #117 (Shape A profile-based auth migration, 5 units). Reauth ran successfully post-merge; validation scrape succeeded on first profile-mode run.

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- All six sources use a uniform scrape-to-data / generate-from-data architecture (`scripts/scrape_*.py` → `data/<src>_$DATE.json` → `scripts/generate_*.py` → `public/feeds/*.xml`)
- Production entrypoint is tracked in git (`scripts/mini_master_update.sh`) — no more untracked wrappers patching the master script at runtime
- Push-conflict recovery uses save / fetch / reset / regenerate (no `git pull --rebase` against generated XMLs)
- Invariant guard between Phase 2 and Phase 3 catches silent scrape regressions (scrape reports success but its dated JSON is missing)
- Comics Kingdom authentication now uses a persistent Chrome profile at `~/.comicskingdom_chrome_profile` (Shape A), matching TinyView's proven pattern and eliminating the WAF slow-walk on the cookie-load startup path
- Chrome boundary instrumentation in `_individual` (and `_secure`) — timestamped log lines at every `driver.get` make hang-site localization a grep
- 254+-test suite passing (first CK-specific tests added this session)
- 312 GoComics feeds, ~153 Comics Kingdom feeds, TinyView feeds, Far Side Daily Dose + New Stuff, New Yorker Daily Cartoon, and 10 Creators feeds updating daily
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled; all CodeQL alerts resolved
- Consistent comic strip sizing (max-width: 700px) and centering across all sources (#105)
- Manual backfill script available for GoComics feed recovery (`scripts/backfill_gocomics_feeds.py`)
- Daily automated feed monitoring via agent

## What's In Progress
<!-- Active work items. Update every session. -->

| Item | Status | Branch | Notes |
|------|--------|--------|-------|
| Shape A (CK profile-based auth) | Monitoring | main (PR #117 merged) | Daytime validation run succeeded (16:12, 153/153, 5s startup). Tonight's 3 AM LaunchD run is the unattended validation. Rollback is a one-line default flip on `setup_driver`. |

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. **Confirm tonight's overnight run.** Grep `logs/master_update.log` tomorrow morning for `load_cookies: driver.get(comicskingdom.com)` — markers should be absent, confirming the production path uses the profile.
2. **Delete `scripts/comicskingdom_scraper_secure.py`** — after a week of clean overnight runs (target: 2026-04-25). Prereq: migrate `scripts/diagnose_ck_page.py` off `_secure` or retire it.
3. **Remove `data/comicskingdom_cookies.pkl` from the repo** — dead data under Shape A. Same week-of-stable-runs gate as `_secure` deletion.
4. **Reauth-script prompt polish.** Current instructions ("Check the reCAPTCHA box in the browser window") don't match reality — CK's CAPTCHA is invisible, and JS-injected credentials get rejected by their bot check. Operator has to manually re-type or paste credentials before clicking Login. Update `scripts/reauth_comicskingdom.py` prompts accordingly.
5. **`chmod 700` on `~/.tinyview_chrome_profile`** — same security fix that Shape A applied to CK's profile. Pre-existing issue with TinyView's `setup_driver`.
6. **Generalize entry-count invariant across sources** — deferred from the original CK reliability plan. Useful across GoComics, TinyView, Creators, etc. Revisit only if partial-scrape incidents become observed.
7. **Investigate issue #91** (GoComics strips don't save to read-later platforms).

## Open Decisions
<!-- Architectural or product decisions that haven't been made yet. -->
<!-- These are the most expensive things to lose between sessions. -->

| Decision | Options Considered | Leaning Toward | Blocking? |
|----------|--------------------|----------------|-----------|
|          |                    |                |           |

## Known Issues
<!-- Bugs, tech debt, or things that are broken but not urgent. -->

- GoComics strips don't save to read-later platforms like Pocket/Instapaper (#91) — approach TBD.
- Old data files (pre-March 31) have fewer entries (~100/day vs 257) than current runs; only ~115 comics matched slugs under the old extraction approach.

## Environment & Setup
<!-- How to run this project. Critical for fresh agent sessions. -->

**Run locally:** `netlify dev` (full stack at `http://localhost:8888`) or `python run_app.py` (Flask at `http://localhost:5001`)
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) — 254 passing, requires Python ≥3.10
**Deploy:** Push to `main` to trigger Netlify deployment
**Key env vars:** `FLASK_DEBUG` (local optional), `NODE_VERSION`, `NETLIFY_FUNCTIONS_DIR`
**Production pipeline:** see [docs/LOCAL_AUTOMATION_README.md](LOCAL_AUTOMATION_README.md) and [docs/DEPLOYMENT.md](DEPLOYMENT.md)

## Architecture Notes
Python package (`comiccaster/`) provides the feed generator and scraper base classes. Source-specific scrapers and generators live in `scripts/`. Netlify serves `public/` as static files; `functions/` holds the OPML-generation and feed-preview serverless functions.

The daily pipeline is three phases, orchestrated by `scripts/local_master_update.sh`:

- **Phase 1 — scrape.** Each source has a dedicated scraper that writes `data/<source>_YYYY-MM-DD.json`.
- **Phase 2 — generate.** Each source has a dedicated generator that reads the latest JSON and writes `public/feeds/*.xml`. All generators are network-free.
- **Phase 3 — commit and push.** If the push is rejected, recovery saves today's JSONs, resets to `origin/main`, restores them, and regenerates all feeds. No `git pull --rebase`.

All scrape outputs are tracked in git as pipeline inputs:

- GoComics → `data/comics_YYYY-MM-DD.json`
- Comics Kingdom → `data/comicskingdom_YYYY-MM-DD.json`
- TinyView → `data/tinyview_YYYY-MM-DD.json`
- New Yorker → `data/newyorker_YYYY-MM-DD.json`
- Far Side → `data/farside_daily_YYYY-MM-DD.json` (per target date) and `data/farside_new_YYYY-MM-DD.json`
- Creators → `data/creators_YYYY-MM-DD.json`

Do not treat these as disposable scratch data. An Apr 9 `.gitignore` cleanup accidentally moved CK JSONs under "ephemeral diagnostics," which contributed to the 2026-04-17 incident chain; corrected the same day.

Between Phase 2 and Phase 3, an invariant guard checks that every successful scrape wrote its dated JSON. A missing file when the scraper returned success is a silent contract violation and is logged as a failure.


## Session Log
<!-- Brief log of recent sessions. Newest first. Delete entries older than 30 days. -->

### 2026-04-18
- **Goal:** Diagnose and fix the Comics Kingdom scraper's chronic ~weekly renderer timeout. Move from "reauth as a reflex" to a structural fix.
- **Accomplished:**
  - Recovered this morning's CK feeds after the 03:13 run failed on the renderer timeout (manual reauth + rescrape, commit `86b3b2883`).
  - Shipped PR #114 (parent plan + Unit 1 instrumentation + Unit 2 smoke tests): added timestamped markers around every Chrome interaction boundary in `_individual`, first CK-specific test coverage (11 tests).
  - Captured two instrumented daytime runs: `_individual` at 14:09 (success, 20.4s on the domain hit), `_secure` at 14:24 (30.0s timeout — reproduced the overnight-failure fingerprint in the afternoon). Data confirmed the WAF slow-walks the first unauthenticated request and the slow-walk is orthogonal to scraper choice.
  - Shipped PR #115 (Unit 1 findings + `_secure` instrumentation): pinned the diagnosis in `docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md`, ruled out Shape B (consolidate on `_secure`).
  - Shipped PR #116 (testenv cleanup, unrelated): cleared all three `Known Issues` items (`bin/chromedriver` ignore, `webdriver-manager` requirement, two test side-effect writes).
  - Shipped PR #117 (Shape A — profile-based auth): 5 implementation units migrated CK auth off pickled cookies and onto a persistent Chrome profile at `~/.comicskingdom_chrome_profile`. `reauth_comicskingdom.py` now imports only from `_individual`, breaking the last production dependency on `_secure`.
  - Seeded the profile post-merge via `python scripts/reauth_comicskingdom.py`; interactive login succeeded in ~15s.
  - Ran validation scrape: 153/153 in a profile-mode run, ~5s startup (vs ~23–33s previously), zero `load_cookies: driver.get` timing markers in the output — the slow-walk code path is confirmed dead on the profile path.
- **Validation:**
  - 276 tests passing (up from 229 pre-session, +11 from PR #114, +14 unlocked by PR #116's `webdriver-manager` install, +22 from PR #117's 5 units).
  - Tonight's 3 AM LaunchD run is the final unattended validation.
- **Didn't finish:** Tonight's overnight run validation (external). Follow-ups queued in `What's Next`: `_secure` deletion, stale pickle removal, reauth prompt polish, TinyView profile `chmod 700`.
- **Discovered:**
  - `_individual` has been the production scraper since 2025-11-15 (commit `d8596247d`), but `_secure` was never fully deprecated — it's imported by both `reauth_comicskingdom.py` and `scripts/diagnose_ck_page.py`. The 2026-04-09 reliability rewrite landed in `_secure` and never reached production. The per-URL strategy of `_individual` (153 sequential page loads) is actually more complete than `_secure`'s favorites-page approach (97/153 on a successful run), so keeping `_individual` as production is the right call.
  - CK uses an invisible reCAPTCHA. JS-injected credential fills get rejected by the bot check; the operator has to manually retype or paste credentials into the login fields. The reauth script's user-facing prompts are wrong about this ("check the reCAPTCHA box" — there is no box). Saved to memory; follow-up fix queued.

### 2026-04-17
- **Goal:** Close the automation gaps exposed by the 2026-04-17 overnight incident (Comics Kingdom feeds missing from the published commit; several source JSONs pushed to `main` with unresolved merge conflict markers). Bring the production entrypoint under version control and replace the push-recovery strategy.
- **Accomplished:**
  - Recovered Comics Kingdom feeds for 2026-04-17 (and fixed 2026-04-16 JSON corruption on `main`) from a dangling local commit (`96f12e820`, `0cbe22e8a`).
  - Brought the update host's wrapper script into git as a minimal env-setter and parametrized the Comics Kingdom invocation so the tracked master script no longer needs runtime text-patching (`f761a9221`).
  - Replaced Phase 3's `git pull --rebase` retry with a save / fetch / reset / regenerate recovery path; added an invariant guard between Phase 2 and Phase 3 (`cead50ac5`).
  - Refactored New Yorker (`062c396d3`), Far Side (`12a735a48`), and Creators (`94c30bff4`) into scrape-to-data / generate-from-data splits. Each split preserves pre-refactor feed output byte-identically; validated by baseline diffs and 31 new unit tests on the pure builder functions.
  - Extended the recovery path to regenerate all six sources from data (`f812c4c18`); recovery now produces byte-identical feeds to a clean run.
  - Rewrote `docs/LOCAL_AUTOMATION_README.md` and `docs/DEPLOYMENT.md` (`ba2a91824`) to describe the current architecture (retired hybrid GHA references).
- **Validation:**
  - 229 tests passing (+31 from this session).
  - Live end-to-end production run at midday succeeded on first push with the new wrapper and reset-on-start policy.
  - Push-conflict recovery validated in a sandbox clone with a divergent origin: first push rejected, staging / reset / restore / regenerate / push-once all worked as designed, divergent commit preserved.
- **Didn't finish:** First unattended overnight run under the new architecture is the next scheduled validation point.
- **Discovered:** The original "CK failed to scrape at 3 AM" story was wrong — the overnight run's CK scrape did succeed; a downstream merge commit landed an unresolved conflict state onto `main`. The 2026-04-16 debug commands inadvertently pushed conflict markers into two other source JSONs in addition to CK's. Investigating the git reflog showed the overnight commit with fresh CK data (`7f76d7adc`) was never reachable from `main` — it was a dangling commit, still recoverable.

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
