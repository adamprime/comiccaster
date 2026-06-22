# Project Status
<!-- Updated: 2026-06-22 by Claude Code -->

## Project Overview
ComicCaster aggregates comics from GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, Mr. Boffo, and first-party external RSS feeds into standards-compliant RSS feeds and OPML bundles. A Python pipeline handles scraping and feed generation where ComicCaster owns the feed; external RSS entries link directly to publisher-provided feeds. Netlify serves the static site and feed files.

## Current State
Stable. Shape A (CK profile-based auth) has been on prod since 2026-04-20 with no observed regressions; daily runs report all-success on most days, with the expected weekly CK session refresh handled manually via `reauth_comicskingdom.py`. Since the last status update, the External RSS catalog (PR #139) and two-pass GoComics scrape (PR #140) both merged, **Mr. Boffo** was added as the seventh self-hosted source (PRs #154–159, including an HTTPS migration that dropped the image proxy), the Far Side proxy was hardened against SSRF (#156), and ChromeDriver now auto-resolves via webdriver-manager (#149). No PRs are open. The dependency stream is current as of 2026-06-22 (pytest 9.1.1, selenium 4.45.0, actions/checkout v7).

**Phase:** Maintenance (active)
**Last Session:** 2026-06-22
**Last Session Summary:** Project review + dependency hygiene. Merged three green Dependabot PRs — #162 (pytest 9.1.0→9.1.1), #161 (selenium 4.44.0→4.45.0), #160 (actions/checkout 6→7) — squash-merged in order, branches deleted, local `main` rebased to `276ae8e63`. Reconciled this STATUS doc with reality (it had drifted ~5 weeks: PR #139 was still listed as open, test count was 289). Current suite: **321 tests collected**.

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- All seven sources use a uniform scrape-to-data / generate-from-data architecture (`scripts/scrape_*.py` → `data/<src>_$DATE.json` → `scripts/generate_*.py` → `public/feeds/*.xml`)
- Production entrypoint is tracked in git (`scripts/mini_master_update.sh`) — no more untracked wrappers patching the master script at runtime
- Push-conflict recovery uses save / fetch / reset / regenerate (no `git pull --rebase` against generated XMLs)
- Invariant guard between Phase 2 and Phase 3 catches silent scrape regressions (scrape reports success but its dated JSON is missing)
- Comics Kingdom authentication uses a persistent Chrome profile at `~/.comicskingdom_chrome_profile` (Shape A); `reauth_comicskingdom.py` is the operator entry point for refresh
- Chrome boundary instrumentation in `_individual` — timestamped log lines at every `driver.get` make hang-site localization a grep
- 321-test suite collected, passing across Python 3.10 / 3.11 / 3.12 (grew from 289 with the Mr. Boffo source and the external-RSS / two-pass GoComics work)
- 312 GoComics feeds, ~153 Comics Kingdom feeds, TinyView feeds, Far Side Daily Dose + New Stuff, New Yorker Daily Cartoon, 10 Creators feeds, and Mr. Boffo (single daily strip) updating daily
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled; **zero open CodeQL alerts**
- Consistent comic strip sizing (max-width: 700px) and centering across all sources (#105)
- Manual backfill script available for GoComics feed recovery (`scripts/backfill_gocomics_feeds.py`)
- Daily automated feed monitoring via agent
- Public feedback site (https://feedback.comiccaster.xyz) auto-tracked: a daily GitHub Action opens an issue for each new post (`feedback-site` label)
- GitHub Actions on Node 24 actions runtime; only 4 active workflows in `.github/workflows/` (down from 8)

## What's In Progress
<!-- Active work items. Update every session. -->

_Nothing in flight. No open PRs; working tree clean on `main`._

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. **`chmod 700` on `~/.tinyview_chrome_profile`** — same security fix that Shape A applied to the CK profile. Pre-existing issue with TinyView's `setup_driver` (`scripts/tinyview_scraper_secure.py:76`).
2. **Audit `SETUP_TINYVIEW_AUTH.sh`** — script is operationally correct (calls `tinyview_scraper_secure.py`, which is the canonical interactive auth tool there). Worth re-reading against the same operator-pragmatic principle the CK setup-doc cleanup applied.
3. **Generalize entry-count invariant across sources** — deferred from the original CK reliability plan. Useful across GoComics, TinyView, Creators, etc. Revisit only if partial-scrape incidents become observed.
4. **Investigate issue #91** (GoComics strips don't save to read-later platforms).
5. **Optional source-code-comment cleanup pass** — several files have docstrings and comments that could be trimmed for accuracy and conciseness. Deferred: low risk, real cost.

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
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) — 289 passing after PR #139 and #140 merge, requires Python ≥3.10
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

### 2026-06-22
- **Goal:** Project review; clear the open dependency PRs.
- **Accomplished:**
  - Got oriented (STATUS had drifted ~5 weeks); confirmed `main` clean.
  - Merged three green Dependabot PRs, squash + delete-branch, in order: #162 (pytest 9.1.0→9.1.1), #161 (selenium 4.44.0→4.45.0), #160 (actions/checkout 6→7). Each touched non-conflicting lines so GitHub rebased cleanly. Rebased local `main` to `276ae8e63`.
  - Reconciled this STATUS doc: PR #139 (merged 2026-05-16) cleared from In Progress, test count corrected 289→321, recent Mr. Boffo / Far Side SSRF / ChromeDriver work folded into Current State, session log pruned to the 30-day window.
- **Validation:** All three PRs were green on CI (Python 3.10/3.11/3.12, CodeQL, coverage, Netlify preview) before merge. Local fast-forward pull verified the expected diff (4 workflow files + `requirements.txt`).
- **Discovered:** The "codecov dependency bumps" the operator spotted were the `codecov/patch` coverage *status check* passing on each PR, not Codecov-action version bumps.

### 2026-06-20 — 2026-06-21 (reconstructed from git; not separately logged at the time)
- **Mr. Boffo added as the seventh self-hosted source** (#154), then iterated: image HTTPS proxy + feed source label (#155), full HTTPS migration dropping the image proxy (#157) with a follow-up for code the migration missed (#158), and docs/CONCEPTS registration (#159). Mr. Boffo is a Daily Dose source (single overwritten image, feed window of one).
- **Far Side proxy hardened against SSRF**, and feed previews now resolve from the current origin (#156).
- **ChromeDriver auto-resolves via webdriver-manager** (#149), removing the manual `bin/chromedriver` pin as a failure point.
- **Catch-up LaunchAgent safety net** for missed overnight runs (#150).

