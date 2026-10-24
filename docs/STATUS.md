# Project Status
<!-- Updated: 2026-10-24 by Claude Code -->

## Project Overview
ComicCaster aggregates comics from GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, Mr. Boffo, and first-party external RSS feeds into standards-compliant RSS feeds and OPML bundles. A Python pipeline handles scraping and feed generation where ComicCaster owns the feed; external RSS entries link directly to publisher-provided feeds. Netlify serves the static site and feed files.

## Current State
Stable. Shape A (CK profile-based auth) has been on prod since 2026-04-20 with no observed regressions; daily runs report all-success on most days, with the expected weekly CK session refresh handled manually via `reauth_comicskingdom.py`. Since the last status update, the External RSS catalog (PR #139) and two-pass GoComics scrape (PR #140) both merged, **Mr. Boffo** was added as the seventh self-hosted source (PRs #154–159, including an HTTPS migration that dropped the image proxy), the Far Side proxy was hardened against SSRF (#156), and ChromeDriver now auto-resolves via webdriver-manager (#149). As of 2026-07-20, **all** Selenium scrapers resolve their driver via `build_chrome_driver` — the last raw-`webdriver.Chrome()` holdout (`tinyview_scraper_secure.py`, which the #149 migration missed and which the nightly TinyView pipeline imports) was closed, ending PATH-driver drift as a source of silent scrape gaps. No PRs are open. The dependency stream is current as of 2026-08-25: **direct** deps (selenium 4.47.0, feedgen 1.0.0, pytest 9.1.1, pytz 2026.3.post1, feedparser 6.0.14, APScheduler 3.11.3, python-dotenv 1.2.3) and, for the first time, **transitive** deps too — the host venv's full 50-package set is now locked in `constraints.txt`, closing a drift channel that had left certifi five months stale while every signal in a dependency PR read as "shipped". On 2026-10-24 the host venv was patched for **CVE-2026-111497** (Brotli decoder memory corruption): brotli 1.2.0 → 1.2.1 via #243.

**Phase:** Maintenance (active)
**Last Session:** 2026-10-24
**Last Session Summary:** Security patch for CVE-2026-111497 (CVSS 9.2, remote, no auth; fixed in PyPI `Brotli` 1.2.1). The scrapers were exposed even though `http_client.py` only sends `Accept-Encoding: gzip, deflate`: urllib3 picks its decoder from the *response's* `Content-Encoding` and adds `br` whenever brotli is importable. CI had been green on 1.2.1 all along, because it installs without the constraints file. The host was still on 1.2.0, because `constraints.txt` pinned it. #243 bumps both files. The host venv is now on 1.2.1 (a `pip freeze` diff shows no other change), and the suite passes **819 tests** in a throwaway venv, in the production venv, and again after Homebrew Node 26.8.1 → 26.12.1. This status file was not updated between 2026-08-25 and this session; `git log` has the work in between (#216 CK post-date identity and vintage reruns, the Far Side morning pass, #240 backup removal, #242 Actions trim).

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- All seven sources use a uniform scrape-to-data / generate-from-data architecture (`scripts/scrape_*.py` → `data/<src>_$DATE.json` → `scripts/generate_*.py` → `public/feeds/*.xml`)
- Production entrypoint is tracked in git (`scripts/mini_master_update.sh`) — no more untracked wrappers patching the master script at runtime
- Push-conflict recovery uses save / fetch / reset / regenerate (no `git pull --rebase` against generated XMLs)
- Invariant guard between Phase 2 and Phase 3 catches silent scrape regressions (scrape reports success but its dated JSON is missing)
- Comics Kingdom authentication uses a persistent Chrome profile at `~/.comicskingdom_chrome_profile` (Shape A); `reauth_comicskingdom.py` is the operator entry point for refresh
- Chrome boundary instrumentation in `_individual` — timestamped log lines at every `driver.get` make hang-site localization a grep
- 819-test suite passing across Python 3.10 / 3.11 / 3.12 in CI and on the host's Python 3.14 venv (499 on 2026-08-25)
- All seven Selenium scrapers build their driver via `comiccaster.webdriver_setup.build_chrome_driver` (webdriver-manager auto-matches ChromeDriver to installed Chrome); no production scraper depends on a PATH-pinned `chromedriver`
- 461 GoComics feeds, 156 Comics Kingdom feeds (147 daily + 9 political), TinyView feeds, Far Side Daily Dose + New Stuff, New Yorker Daily Cartoon, 10 Creators feeds, and Mr. Boffo (single daily strip) updating daily. CK moved 153 → 150 on 2026-08-24: four comics (broomhilda, edge-city, pluggers, shoe) were reassigned to GoComics, and `edge-city-classic` was added for CK's separate run of Edge City. CK moved 150 → 156 on 2026-09-28, when the CK loaders began reading `political_comics_list.json`: six cartoonists listed only there had never been scraped
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled; **zero open CodeQL alerts**
- Secret scanning **with push protection** (push protection since 2026-10-24): a push containing a recognized credential is rejected, not just reported afterwards. There were zero secret-scanning alerts in the repo's history when it was turned on, so the pipeline's feed and data commits have never matched a pattern. If a Pass 1/2 push ever fails with `GH013` / "push protection", the cause is a flagged secret in the commit, not git or SSH. Don't bypass it; find out what leaked into `data/` or `public/feeds/` first (see `SECURITY.md`)
- Dependabot alerts and Dependabot security-update PRs enabled (security PRs since 2026-10-24). Merging a security PR still doesn't patch the host. Run the venv install afterwards (see `docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md`)
- Consistent comic strip sizing (max-width: 700px) and centering across all sources (#105)
- GoComics recovery: `scripts/authenticated_scraper_secure.py --backfill-days N` (Pass 2 runs a rolling backfill daily)
- Daily automated feed monitoring via agent
- Public feedback site (https://feedback.comiccaster.xyz) auto-tracked: a daily GitHub Action opens an issue for each new post (`feedback-site` label)
- GitHub Actions on Node 24 actions runtime; only 4 active workflows in `.github/workflows/` (down from 8)

## What's In Progress
<!-- Active work items. Update every session. -->

_Nothing in flight. No open PRs; working tree clean on `main`._

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. **(Parked 2026-08-25 — operator: no action needed.)** ~~Restore the Far Side New Stuff scrape~~ — `docs/plans/2026-08-02-001-fix-farside-new-stuff-cursor-plan.md`. The feed has been empty since launch; bot protection blocks the scraper. Keeping the feed is already decided; what's open is whether New Stuff is a browsable archive or a rotating window (which decides whether the cursor's `>` guard is correct), and that can't be settled until the block is cleared. Not urgent — `farside_new` is exempt at minimum 0 in `SOURCE_RULES` by design, so it never trips the guard. **The operator re-confirmed on 2026-08-25 that New Stuff has been completely static**, so a working scraper would recover the existing back catalogue and nothing more. Parked deliberately, not forgotten: pick it up only if New Stuff starts publishing again, or if the empty feed itself becomes a complaint.

_Done 2026-08-05, previously listed here: **generalize the entry-count invariant across sources** — `298e547fdb` gave all 8 sources a minimum in `SOURCE_RULES`, so a scrape that writes a file but no data now fails._

_Cleared 2026-08-24/25: merged all five open Dependabot PRs (#163, #170, #182, #186, #189) plus feedgen 1.0.0 (#192); pinned setup-chrome (#190); put the shipped npm dep under Dependabot (#191); fixed the cross-source feed collision (#193); completed a four-stage transitive refresh and locked it in `constraints.txt`._

## Open Decisions
<!-- Architectural or product decisions that haven't been made yet. -->
<!-- These are the most expensive things to lose between sessions. -->

| Decision | Options Considered | Leaning Toward | Blocking? |
|----------|--------------------|----------------|-----------|
|          |                    |                |           |

_Decided 2026-10-24: **Dependabot security updates turned on** (operator call: "the more places sharing security info with us the better"). Alerts were already on; security-fix PRs were off, so brotli 1.2.1 would have waited for the weekly version-update run. Security PRs only open once GitHub publishes an advisory, so outside briefs still matter._

## Known Issues
<!-- Bugs, tech debt, or things that are broken but not urgent. -->

- GoComics strips don't save to read-later platforms like Pocket/Instapaper (#91) — **closed WONTFIX (2026-06-09).** Read-later apps re-fetch the linked page and extract the image themselves; GoComics' page/image delivery doesn't expose it in a form they can pull. The only fix is self-hosting the images, which we won't do. Not actionable; don't reopen.
- Old data files (pre-March 31) have fewer entries (~100/day vs 257) than current runs; only ~115 comics matched slugs under the old extraction approach.

## Environment & Setup
<!-- How to run this project. Critical for fresh agent sessions. -->

**Run locally:** `netlify dev` (full stack at `http://localhost:8888`) or `python run_app.py` (Flask at `http://localhost:5001`)
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) — 819 passing, requires Python ≥3.10 (on the host, bare `python3` is Apple's 3.9.6; build venvs from `/opt/homebrew/opt/python@3.14/bin/python3.14`, the production venv's base)
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

### 2026-10-24
- **Goal:** Patch CVE-2026-111497 (Brotli decoder memory corruption, CVSS 9.2) on the pipeline host, working from the operator's vulnerability brief.
- **Accomplished:**
  - **#243:** `constraints.txt` `brotli==1.2.0` → `1.2.1`, and `requirements.txt` `brotli>=1.2.0` → `>=1.2.1`. No other pins changed. Built in a worktree, tested in a throwaway venv, merged once CI passed.
  - **Host venv:** `pip show brotli` went from 1.2.0 to 1.2.1. A `pip freeze` diff from before and after the install shows only that line changed. The suite passed 819 in the production venv, and again after Homebrew Node 26.8.1 → 26.12.1.
  - **Why the host was exposed while CI was green:** CI installs without `constraints.txt` and already resolved 1.2.1. The host lock is what kept 1.2.0. Added to `docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md`.
  - **Brief corrections:** bare `python3` on the host is 3.9.6 (too old for the repo), and Pass 1/2 never pull; they run `git reset --hard origin/main`, so stray edits in the pipeline clone are wiped, not rejected.
- **Repo security settings (operator call):** turned on Dependabot security-update PRs and secret-scanning push protection.
- **Not ComicCaster, handed off:** Homebrew's `node` uses Homebrew's shared libbrotli, and the long-running OpenClaw processes still had the old Node and brotli 1.2.0 loaded after the upgrade. That's for the OpenClaw/Homebrew owner. The ComicCaster pipeline and tests never use the host's Node.
