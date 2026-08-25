# Project Status
<!-- Updated: 2026-08-25 by Claude Code -->

## Project Overview
ComicCaster aggregates comics from GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, Mr. Boffo, and first-party external RSS feeds into standards-compliant RSS feeds and OPML bundles. A Python pipeline handles scraping and feed generation where ComicCaster owns the feed; external RSS entries link directly to publisher-provided feeds. Netlify serves the static site and feed files.

## Current State
Stable. Shape A (CK profile-based auth) has been on prod since 2026-04-20 with no observed regressions; daily runs report all-success on most days, with the expected weekly CK session refresh handled manually via `reauth_comicskingdom.py`. Since the last status update, the External RSS catalog (PR #139) and two-pass GoComics scrape (PR #140) both merged, **Mr. Boffo** was added as the seventh self-hosted source (PRs #154–159, including an HTTPS migration that dropped the image proxy), the Far Side proxy was hardened against SSRF (#156), and ChromeDriver now auto-resolves via webdriver-manager (#149). As of 2026-07-20, **all** Selenium scrapers resolve their driver via `build_chrome_driver` — the last raw-`webdriver.Chrome()` holdout (`tinyview_scraper_secure.py`, which the #149 migration missed and which the nightly TinyView pipeline imports) was closed, ending PATH-driver drift as a source of silent scrape gaps. No PRs are open. The dependency stream is current as of 2026-08-25: **direct** deps (selenium 4.47.0, feedgen 1.0.0, pytest 9.1.1, pytz 2026.3.post1, feedparser 6.0.14, APScheduler 3.11.3, python-dotenv 1.2.3) and, for the first time, **transitive** deps too — the host venv's full 50-package set is now locked in `constraints.txt`, closing a drift channel that had left certifi five months stale while every signal in a dependency PR read as "shipped".

**Phase:** Maintenance (active)
**Last Session:** 2026-08-25
**Last Session Summary:** Dependency sweep + a subscriber-visible feed bug found while doing it. (1) Cleared the entire Dependabot backlog and bumped feedgen 0.9.0 → 1.0.0, which had been frozen 2.5 years because closing PR #4 in 2025 permanently suppressed that version. (2) Found the host venv was two selenium minors behind `requirements.txt` — merging dependency PRs never touched `venv/`, so bumps weren't reaching production. (3) Ran a four-stage transitive refresh (certifi → lxml/soupsieve → urllib3/idna/charset-normalizer → the rest) and locked all 50 packages in `constraints.txt`. (4) Fixed a cross-source collision: four slugs were claimed by both GoComics and Comics Kingdom, so the two generators overwrote each other twice daily and subscribers got every strip twice. Edge City turned out to be two genuinely different runs (GoComics ©2011, CK ©2006), so CK's became `edge-city-classic`, backfilled to 87 entries. Current suite: **499 tests** passing.

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- All seven sources use a uniform scrape-to-data / generate-from-data architecture (`scripts/scrape_*.py` → `data/<src>_$DATE.json` → `scripts/generate_*.py` → `public/feeds/*.xml`)
- Production entrypoint is tracked in git (`scripts/mini_master_update.sh`) — no more untracked wrappers patching the master script at runtime
- Push-conflict recovery uses save / fetch / reset / regenerate (no `git pull --rebase` against generated XMLs)
- Invariant guard between Phase 2 and Phase 3 catches silent scrape regressions (scrape reports success but its dated JSON is missing)
- Comics Kingdom authentication uses a persistent Chrome profile at `~/.comicskingdom_chrome_profile` (Shape A); `reauth_comicskingdom.py` is the operator entry point for refresh
- Chrome boundary instrumentation in `_individual` — timestamped log lines at every `driver.get` make hang-site localization a grep
- 499-test suite passing across Python 3.10 / 3.11 / 3.12 (grew from 341 with catalog source-integrity guards, GoComics source-ownership tests, and `source_slug` coverage)
- All seven Selenium scrapers build their driver via `comiccaster.webdriver_setup.build_chrome_driver` (webdriver-manager auto-matches ChromeDriver to installed Chrome); no production scraper depends on a PATH-pinned `chromedriver`
- 461 GoComics feeds, 150 Comics Kingdom feeds, TinyView feeds, Far Side Daily Dose + New Stuff, New Yorker Daily Cartoon, 10 Creators feeds, and Mr. Boffo (single daily strip) updating daily. CK moved 153 → 150 on 2026-08-24: four comics (broomhilda, edge-city, pluggers, shoe) were reassigned to GoComics, and `edge-city-classic` was added for CK's separate run of Edge City
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

1. **Restore the Far Side New Stuff scrape** — `docs/plans/2026-08-02-001-fix-farside-new-stuff-cursor-plan.md`. The feed has been empty since launch; bot protection blocks the scraper. Keeping the feed is already decided; what's open is whether New Stuff is a browsable archive or a rotating window (which decides whether the cursor's `>` guard is correct), and that can't be settled until the block is cleared. Not urgent — `farside_new` is exempt at minimum 0 in `SOURCE_RULES` by design, so it never trips the guard.

_Done 2026-08-05, previously listed here: **generalize the entry-count invariant across sources** — `298e547fdb` gave all 8 sources a minimum in `SOURCE_RULES`, so a scrape that writes a file but no data now fails._

_Cleared 2026-08-24/25: merged all five open Dependabot PRs (#163, #170, #182, #186, #189) plus feedgen 1.0.0 (#192); pinned setup-chrome (#190); put the shipped npm dep under Dependabot (#191); fixed the cross-source feed collision (#193); completed a four-stage transitive refresh and locked it in `constraints.txt`._

## Open Decisions
<!-- Architectural or product decisions that haven't been made yet. -->
<!-- These are the most expensive things to lose between sessions. -->

| Decision | Options Considered | Leaning Toward | Blocking? |
|----------|--------------------|----------------|-----------|
|          |                    |                |           |

## Known Issues
<!-- Bugs, tech debt, or things that are broken but not urgent. -->

- GoComics strips don't save to read-later platforms like Pocket/Instapaper (#91) — **closed WONTFIX (2026-06-09).** Read-later apps re-fetch the linked page and extract the image themselves; GoComics' page/image delivery doesn't expose it in a form they can pull. The only fix is self-hosting the images, which we won't do. Not actionable; don't reopen.
- Old data files (pre-March 31) have fewer entries (~100/day vs 257) than current runs; only ~115 comics matched slugs under the old extraction approach.

## Environment & Setup
<!-- How to run this project. Critical for fresh agent sessions. -->

**Run locally:** `netlify dev` (full stack at `http://localhost:8888`) or `python run_app.py` (Flask at `http://localhost:5001`)
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) — 499 passing, requires Python ≥3.10
**Install (pipeline host):** `venv/bin/python -m pip install -r requirements.txt -c constraints.txt` — the constraints file pins transitives so the host venv is reproducible; CI deliberately installs unconstrained as a canary
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

### 2026-08-24 / 2026-08-25
- **Goal:** Clear the open Dependabot PRs, then whatever else the sweep turned up.
- **Accomplished:**
  - Merged all five open Dependabot PRs (#163 apscheduler, #170 pytz, #182 feedparser, #186 selenium 4.47.0, #189 python-dotenv) after testing the combined set in a throwaway venv rather than trusting five independent CI runs. #186/#189 needed a Dependabot rebase after the first merges.
  - **feedgen 0.9.0 → 1.0.0 (#192).** It builds every feed we serve and had been stuck 2.5 years — Dependabot proposed it in PR #4, that PR was closed unmerged on 2025-06-25, and closing a Dependabot PR permanently suppresses that version. Verified beyond the (heavily mocked) unit suite: generated feed XML from real scraped data was byte-identical between versions once the timestamp was normalized. Same discovery pattern retired `requests-mock`, which was pinned, suppressed by the same 2025 batch-close, and used by zero tests.
  - **The host venv had drifted from `requirements.txt`** (selenium 4.44.0 installed vs 4.46.0 pinned). CI installs fresh so it always tests the new version; Netlify redeploys on push; the nightly run keeps reporting ALL SUCCESS — none of which touch `venv/`, which is what the scrapers actually execute. Captured as `docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md`.
  - **Four-stage transitive refresh**, one group at a time with a gate each: certifi; lxml/soupsieve; urllib3/idna/charset-normalizer; then the remainder incl. tzlocal. Ended with `constraints.txt` locking all 50 packages. Two findings worth keeping: lxml reaches production only through feedgen (all 22 BeautifulSoup calls use `'html.parser'`), so the feed-XML diff was the gate that mattered; and a New Yorker payload that looked like a parsing regression was upstream drift — proven by re-scraping on the OLD libraries in the same minute. A baseline taken hours earlier is not a control.
  - **Fixed a cross-source feed collision (#193).** `broomhilda`, `edge-city`, `pluggers`, `shoe` were claimed by both GoComics and Comics Kingdom; both generators write `public/feeds/<slug>.xml`, so pass 1 (ending with CK) and pass 2 (GoComics alone) overwrote each other daily — changing `<guid>` each time, so subscribers received every strip twice. Root cause was two layers: commit `11e401b688` (2025-11-15) stamped `source: comicskingdom` onto pre-existing GoComics entries without updating their `url`, and `generate_gocomics_feeds.py` filtered on nothing while the CK generator had always filtered on `source`.
  - **Edge City needed a different fix from the other three.** Broom Hilda / Pluggers / Shoe are identical strips from two distributors (perceptual correlation r≈0.99 same-day), so the tiebreak was delivery reliability — GoComics 83/83 days vs CK 79–80/83. Edge City is two genuinely different runs: GoComics ©2011, CK ©2006, with no correlation at any offset in a ±16-day window. CK's run became `edge-city-classic` via a new `source_slug` field, backfilled from 276 days of its own history (filed under the old shared slug) to 87 entries.
  - Also: pinned `browser-actions/setup-chrome` to `@v2` (#190) — it was floating on `@latest` in the workflow that gates every PR; and pointed Dependabot's npm config at `/` (#191), which had been managing two unused packages while ignoring `rss-parser`, the only npm package that actually ships.
- **Verification:** ran a full Pass 1 manually (all seven sources green) to prove the collision fix in production; the unattended 03:05 run on 08-25 then validated the dependency work — all 8 invariants passed, CK exactly 150, GoComics 243, no mojibake, no issues opened.

### 2026-07-20
- **Goal:** Evaluate/merge Dependabot PRs #166 & #167; review this morning's TinyView reauth output.
- **Accomplished:**
  - Merged two green Dependabot PRs (squash + delete-branch): #166 (actions/setup-python 6→7) and #167 (selenium 4.45.0→4.46.0). #166 is a major bump but its breaking changes don't apply (removed `pip-install` input unused; dropped EOL Pythons 3.7–3.9, we run 3.10–3.12), and CI ran the test matrix on v7 itself.
  - **Root-caused the TinyView reauth warning + a silent Jul 19–20 data gap.** `scripts/tinyview_scraper_secure.py::setup_driver` still built its driver with raw `webdriver.Chrome()`, so it leaned on a PATH `chromedriver` — the #149 (2026-06-09) webdriver-manager migration had missed this one script. Because the nightly `tinyview_scraper_local_authenticated.py` imports `setup_driver` from it, that single raw constructor was the driver source for the whole TinyView pipeline; it drifted when Chrome auto-updated 149→150 and the scrape stopped producing data.
  - **Fixed it** (`fix`): routed `setup_driver` through `comiccaster.webdriver_setup.build_chrome_driver`, matching CK/GoComics/Far Side. Updated the 5 existing profile tests to patch the helper and added a guard test (`TestSetupDriverBuilder`) asserting the shared helper is used, not a raw driver (+1 → 341 total).
  - **Recovered the gap:** manual rescrape resolved chromedriver 150.0.7871.124 to match Chrome 150 via webdriver-manager (bypassing the stale PATH binary), wrote `data/tinyview_2026-07-20.json` (4 comics), and regenerated/pushed the affected feeds (itchy-feet, nick-anderson, student-bill, the-other-end).
  - Captured the fix as `docs/solutions/best-practices/scrapers-must-use-build-chrome-driver.md`.
- **Validation:** Full suite **341 passing** across 3.10/3.11/3.12. Driver fix verified end-to-end by the live rescrape (correct driver auto-resolved, data landed, exit 0). Comics Kingdom confirmed already on the helper — no action needed.
- **Discovered:**
  - `tinyview_scraper_secure.py` is imported by the nightly pipeline script, so its "reauth-only" driver setup is actually production-critical.
  - `brew upgrade chromedriver` is a dead end: the formula is deprecated and the upgrade left PATH at 151 (ahead of Chrome 150). The webdriver-manager helper makes the PATH driver irrelevant for all production scrapers; `chromedriver --version` even hangs on this box.
  - The `⚠️ No Firebase auth keys found` line in TinyView reauth is cosmetic (session persists via cookies, not localStorage), not a failure signal.

### 2026-06-22
- **Goal:** Project review; clear the open dependency PRs.
- **Accomplished:**
  - Got oriented (STATUS had drifted ~5 weeks); confirmed `main` clean.
  - Merged three green Dependabot PRs, squash + delete-branch, in order: #162 (pytest 9.1.0→9.1.1), #161 (selenium 4.44.0→4.45.0), #160 (actions/checkout 6→7). Each touched non-conflicting lines so GitHub rebased cleanly. Rebased local `main` to `276ae8e63`.
  - Reconciled this STATUS doc: PR #139 (merged 2026-05-16) cleared from In Progress, recent Mr. Boffo / Far Side SSRF / ChromeDriver work folded into Current State, session log pruned to the 30-day window.
  - Then worked the backlog:
    - **TinyView profile `chmod 700`** (`fix`, with tests): `setup_driver` now tightens `~/.tinyview_chrome_profile` to `0o700`, matching CK Shape A. Added `tests/test_tinyview_scraper_secure.py` (+5 tests → 326 total).
    - **Audited `SETUP_TINYVIEW_AUTH.sh`** and fixed a real path-resolution bug (`fix`): the scripts/ reorg (`bf4e41d01`) left it resolving venv/.env/data as if at repo root, so venv activation silently fell back to system Python and the cookie pickle landed in `scripts/data/` while the daily run reads root `data/`. (Auth had survived only because the Chrome profile path is absolute.) Now resolves `PROJECT_ROOT` to the parent and invokes the scraper by its scripts/ path.
    - **Comment/docstring cleanup sweep** (`docs`): 12 scraper/library files + 1 archived note. Concision, accuracy fixes (loader/gocomics no longer claim JSON-LD; scraper_factory described as a source registry, not a "singleton"; mrboffo `secure_daily` marker), and softened method-revealing/WAF-product-naming prose. Verified the code-token stream is byte-identical and the suite stayed green (326) — comments/docstrings only.
    - **Issue #91 (GoComics → read-later): recorded WONTFIX** (already closed 2026-06-09) in Known Issues + auto-memory.
- **Validation:** All three Dependabot PRs were green on CI before merge; local fast-forward verified the expected diff. Full suite **326 passing** after the chmod fix and cleanup sweep. Cleanup verified non-behavioral via a token-stream comparison against HEAD.
- **Discovered:**
  - The "codecov dependency bumps" the operator spotted were the `codecov/patch` coverage *status check* passing on each PR, not Codecov-action version bumps.
  - `SETUP_TINYVIEW_AUTH.sh` had been quietly half-broken since the scripts/ reorg; it only "worked" because the absolute-path Chrome profile masked the misplaced cookie/.env/venv paths. The prior "operationally correct" note had only checked which tool it calls, not its path resolution.

### 2026-06-20 — 2026-06-21 (reconstructed from git; not separately logged at the time)
- **Mr. Boffo added as the seventh self-hosted source** (#154), then iterated: image HTTPS proxy + feed source label (#155), full HTTPS migration dropping the image proxy (#157) with a follow-up for code the migration missed (#158), and docs/CONCEPTS registration (#159). Mr. Boffo is a Daily Dose source (single overwritten image, feed window of one).
- **Far Side proxy hardened against SSRF**, and feed previews now resolve from the current origin (#156).
- **ChromeDriver auto-resolves via webdriver-manager** (#149), removing the manual `bin/chromedriver` pin as a failure point.
- **Catch-up LaunchAgent safety net** for missed overnight runs (#150).

