# Project Status
<!-- Updated: 2026-10-24 by Claude Code -->

## Project Overview
ComicCaster aggregates comics from GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, Mr. Boffo, and first-party external RSS feeds into standards-compliant RSS feeds and OPML bundles. A Python pipeline handles scraping and feed generation where ComicCaster owns the feed; external RSS entries link directly to publisher-provided feeds. Netlify serves the static site and feed files.

## Current State
Stable. Shape A (CK profile-based auth) has been on prod since 2026-04-20 with no observed regressions; daily runs report all-success on most days, with the expected weekly CK session refresh handled manually via `reauth_comicskingdom.py`. Since the last status update, the External RSS catalog (PR #139) and two-pass GoComics scrape (PR #140) both merged, **Mr. Boffo** was added as the seventh self-hosted source (PRs #154–159, including an HTTPS migration that dropped the image proxy), the Far Side proxy was hardened against SSRF (#156), and ChromeDriver now auto-resolves via webdriver-manager (#149). As of 2026-07-20, **all** Selenium scrapers resolve their driver via `build_chrome_driver` — the last raw-`webdriver.Chrome()` holdout (`tinyview_scraper_secure.py`, which the #149 migration missed and which the nightly TinyView pipeline imports) was closed, ending PATH-driver drift as a source of silent scrape gaps. No PRs are open. The dependency stream is current as of 2026-08-25: **direct** deps (selenium 4.47.0, feedgen 1.0.0, pytest 9.1.1, pytz 2026.3.post1, feedparser 6.0.14, APScheduler 3.11.3, python-dotenv 1.2.3) and, for the first time, **transitive** deps too — the host venv's full 50-package set is now locked in `constraints.txt`, closing a drift channel that had left certifi five months stale while every signal in a dependency PR read as "shipped". On 2026-10-24 the host venv was patched for **CVE-2026-111497** (Brotli decoder memory corruption): brotli 1.2.0 → 1.2.1 via #243. Later that day six more PRs merged. #244 closed an open proxy: the feed-preview function now fetches only ComicCaster's own feeds and the listed external feeds. #245 added a daily audit of the host venv against the OSV vulnerability database, and removed APScheduler, tzlocal and requests-toolbelt. #246 made the site readable by agents (`public/catalog.json`, cross-origin headers on feeds, `llms.txt`, `robots.txt`). #247 pinned certifi 2026.10.19 for the compromised emSign CA keys, and the host's pip went to 26.2.2 because pip bundles its own certifi. #248 made Spanish-tab feeds declare `<language>es</language>`. #249 made CI test the host's pinned versions, with a weekly unconstrained canary.

**Phase:** Maintenance (active)
**Last Session:** 2026-10-24
**Last Session Summary:** The operator asked whether to rewrite ComicCaster in Rust after a week of security news. The answer was no. Python is already memory-safe, Chrome stays in any rewrite, and the risks found were logic, config and patching gaps, which Rust does not prevent. One orchestrating session and two side sessions then fixed what the review found, in six PRs (#244–#249, see Current State). The host now runs pip 26.2.2 and certifi 2026.10.19, its audit is clean across 46 packages, and the suite passes **942 tests** on combined `main`. Lessons: `docs/solutions/best-practices/parallel-sessions-on-the-live-pipeline-checkout.md` and `docs/solutions/best-practices/github-merge-without-required-checks.md`.

**Earlier session the same day:** Security patch for CVE-2026-111497 (CVSS 9.2, remote, no auth; fixed in PyPI `Brotli` 1.2.1). The scrapers were exposed even though `http_client.py` only sends `Accept-Encoding: gzip, deflate`: urllib3 picks its decoder from the *response's* `Content-Encoding` and adds `br` whenever brotli is importable. CI had been green on 1.2.1 all along, because it installs without the constraints file. The host was still on 1.2.0, because `constraints.txt` pinned it. #243 bumps both files. The host venv is now on 1.2.1 (a `pip freeze` diff shows no other change), and the suite passes **819 tests** in a throwaway venv, in the production venv, and again after Homebrew Node 26.8.1 → 26.12.1. This status file was not updated between 2026-08-25 and this session; `git log` has the work in between (#216 CK post-date identity and vintage reruns, the Far Side morning pass, #240 backup removal, #242 Actions trim).

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- All seven sources use a uniform scrape-to-data / generate-from-data architecture (`scripts/scrape_*.py` → `data/<src>_$DATE.json` → `scripts/generate_*.py` → `public/feeds/*.xml`)
- Production entrypoint is tracked in git (`scripts/mini_master_update.sh`) — no more untracked wrappers patching the master script at runtime
- Push-conflict recovery uses save / fetch / reset / regenerate (no `git pull --rebase` against generated XMLs)
- Invariant guard between Phase 2 and Phase 3 catches silent scrape regressions (scrape reports success but its dated JSON is missing)
- Comics Kingdom authentication uses a persistent Chrome profile at `~/.comicskingdom_chrome_profile` (Shape A); `reauth_comicskingdom.py` is the operator entry point for refresh
- Chrome boundary instrumentation in `_individual` — timestamped log lines at every `driver.get` make hang-site localization a grep
- 942-test suite passing on Python 3.14, the host's version, both in CI and in the host venv (819 on the morning of 2026-10-24, 499 on 2026-08-25). Since #249, CI's Tests job installs with `-c constraints.txt`, so a green PR has tested what the host runs. The weekly `dependency-canary.yml` (Mondays 10:17 UTC, never on PRs) installs unconstrained to catch a new upstream release that breaks us
- All seven Selenium scrapers build their driver via `comiccaster.webdriver_setup.build_chrome_driver` (webdriver-manager auto-matches ChromeDriver to installed Chrome); no production scraper depends on a PATH-pinned `chromedriver`
- 461 GoComics feeds, 156 Comics Kingdom feeds (147 daily + 9 political), TinyView feeds, Far Side Daily Dose + New Stuff, New Yorker Daily Cartoon, 10 Creators feeds, and Mr. Boffo (single daily strip) updating daily. CK moved 153 → 150 on 2026-08-24: four comics (broomhilda, edge-city, pluggers, shoe) were reassigned to GoComics, and `edge-city-classic` was added for CK's separate run of Edge City. CK moved 150 → 156 on 2026-09-28, when the CK loaders began reading `political_comics_list.json`: six cartoonists listed only there had never been scraped
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled; **zero open CodeQL alerts**
- Secret scanning **with push protection** (push protection since 2026-10-24): a push containing a recognized credential is rejected, not just reported afterwards. There were zero secret-scanning alerts in the repo's history when it was turned on, so the pipeline's feed and data commits have never matched a pattern. If a Pass 1/2 push ever fails with `GH013` / "push protection", the cause is a flagged secret in the commit, not git or SSH. Don't bypass it; find out what leaked into `data/` or `public/feeds/` first (see `SECURITY.md`)
- Dependabot alerts and Dependabot security-update PRs enabled (security PRs since 2026-10-24). Merging a security PR still doesn't patch the host. Run the venv install afterwards (see `docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md`). Alerts only cover `requirements.txt` and `setup.py`, because GitHub's dependency graph doesn't read `constraints.txt`. Indirect dependencies, such as certifi, are covered by the host audit below
- Daily host vulnerability audit (#245): each Pass 1 checks every package installed in the host venv against OSV (`scripts/check_vulnerabilities.py`). A hit opens a deliberately generic `vulnaudit` issue that doesn't name the package, so run the script on the host for details. If OSV is unreachable it only warns. It can't see pip's own bundled certifi, so upgrade pip on the host when a certifi advisory lands
- Feed-preview function locked down (#244): `functions/fetch-feed.js` fetches only `/feeds/<slug>.xml` on ComicCaster's own hosts (production, deploy previews, and localhost in dev) and exact listed external `feed_url`s, and it never follows redirects
- Agent access (#246): `public/catalog.json` lists every comic with one schema (694 entries, 688 with a feed). It is rebuilt by Pass 1, Pass 2 and their push recovery. `public/llms.txt` and `robots.txt` point agents at it, and feeds, `/rss/*` and the catalog send `Access-Control-Allow-Origin: *`
- Spanish feeds declare `<language>es</language>` (#248), driven by `language: es` on the comic's Daily-list entry and enforced by a test against the Spanish tab
- Consistent comic strip sizing (max-width: 700px) and centering across all sources (#105)
- GoComics recovery: `scripts/authenticated_scraper_secure.py --backfill-days N` (Pass 2 runs a rolling backfill daily)
- Daily automated feed monitoring via agent
- Public feedback site (https://feedback.comiccaster.xyz) auto-tracked: a daily GitHub Action opens an issue for each new post (`feedback-site` label)
- GitHub Actions on Node 24 actions runtime; 7 workflows in `.github/workflows/` (claude, codeql, dependency-canary, pipeline-alert, pipeline-heartbeat, tests, watch-feedback). No check is *required* to merge: the `main-branch-protection` ruleset is disabled, and auto-merge is off in the repo settings. "Merge when green" therefore means reading the checks for the PR's head commit yourself (see `docs/solutions/best-practices/github-merge-without-required-checks.md`)

## What's In Progress
<!-- Active work items. Update every session. -->

_Nothing in flight. No open PRs; working tree clean on `main`._

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. **Watch the first live runs of the 2026-10-24 changes.** The catalog rebuild has already run live once: the 2026-10-24 13:02 Pass 2 logged `✅ Catalog rebuilt` (694 comics) and ALL SUCCESS. Pass 1 on 2026-10-25 at 03:05 is the first scheduled run of the vulnerability audit. It should open no `vulnaudit` issue, its log should show `✅ Catalog build succeeded`, and it should rewrite the 52 active Spanish feeds with `<language>es</language>`. The four dormant ones stay `en` until they publish again. The first `dependency-canary` run is Monday 10:17 UTC. A scheduled workflow's failure email goes to whoever last edited its cron, so confirm the operator actually receives one before relying on it.
2. **Agent access, next steps.** Plan: `docs/plans/2026-10-24-1300-feat-agent-access-next-steps-plan.md` (strip images as `media:content`, an OPML link that works with GET, then a read-only MCP server).
3. **(Parked 2026-08-25 — operator: no action needed.)** ~~Restore the Far Side New Stuff scrape~~ — `docs/plans/2026-08-02-001-fix-farside-new-stuff-cursor-plan.md`. The feed has been empty since launch; bot protection blocks the scraper. Keeping the feed is already decided; what's open is whether New Stuff is a browsable archive or a rotating window (which decides whether the cursor's `>` guard is correct), and that can't be settled until the block is cleared. Not urgent — `farside_new` is exempt at minimum 0 in `SOURCE_RULES` by design, so it never trips the guard. **The operator re-confirmed on 2026-08-25 that New Stuff has been completely static**, so a working scraper would recover the existing back catalogue and nothing more. Parked deliberately, not forgotten: pick it up only if New Stuff starts publishing again, or if the empty feed itself becomes a complaint.

_Done 2026-08-05, previously listed here: **generalize the entry-count invariant across sources** — `298e547fdb` gave all 8 sources a minimum in `SOURCE_RULES`, so a scrape that writes a file but no data now fails._

_Cleared 2026-08-24/25: merged all five open Dependabot PRs (#163, #170, #182, #186, #189) plus feedgen 1.0.0 (#192); pinned setup-chrome (#190); put the shipped npm dep under Dependabot (#191); fixed the cross-source feed collision (#193); completed a four-stage transitive refresh and locked it in `constraints.txt`._

## Open Decisions
<!-- Architectural or product decisions that haven't been made yet. -->
<!-- These are the most expensive things to lose between sessions. -->

| Decision | Options Considered | Leaning Toward | Blocking? |
|----------|--------------------|----------------|-----------|
| Delete `public/feeds/everyday-people-cartoons.xml`? It is frozen at 2025-04-09, the comic was delisted in #140, and the catalog leaves it out via a `RETIRED_FEEDS` allowlist | Delete the file and the allowlist entry; or keep it for anyone still subscribed | None (operator's call) | No |
| Two listed external feeds return HTTP 500 (checked 2026-10-24): Awkward Zombie and Wilde Life | Find a new feed URL; drop them from `external_comics_list.json`; or wait to see whether the sites recover | Wait a week, then decide | No |
| Make Tests a *required* check on `main`? | Re-enable the ruleset with Tests required; or keep relying on whoever merges to read the checks | Undecided. Enabled as written, the disabled ruleset would block every merge. It requires a check named `Tests`, but the job reports as `test`. It demands one approving review, which a solo maintainer can't give to their own PR. It has no bypass actors, so it would also block the pipeline's direct pushes to `main`. `tests.yml` also skips feeds, data and docs, so a required Tests check would never start on those changes. Re-enabling needs a bypass for the pipeline's pushes | No |

_Decided 2026-10-24 (afternoon): **no Rust rewrite.** **CI tests `constraints.txt`** (#249), keeping a weekly unconstrained canary. **certifi 2026.10.19, not 2026.10.23**: 10.19 is the PSF-recommended fix, and 10.23 is an automated sync that drops two emSign roots 10.19 had restored as unaffected. **Upgrade the host's pip to 26.2.2** from a hash-pinned wheel, because pip uses its own bundled certifi in addition to the installed one._

_Decided 2026-10-24: **Dependabot security updates turned on** (operator call: "the more places sharing security info with us the better"). Alerts were already on; security-fix PRs were off, so brotli 1.2.1 would have waited for the weekly version-update run. Security PRs only open once GitHub publishes an advisory, so outside briefs still matter._

## Known Issues
<!-- Bugs, tech debt, or things that are broken but not urgent. -->

- GoComics strips don't save to read-later platforms like Pocket/Instapaper (#91) — **closed WONTFIX (2026-06-09).** Read-later apps re-fetch the linked page and extract the image themselves; GoComics' page/image delivery doesn't expose it in a form they can pull. The only fix is self-hosting the images, which we won't do. Not actionable; don't reopen.
- Previewing Dumbing of Age on the site fails ("Failed to fetch or parse feed"). It failed the same way before #244, and the feed loads fine from the host, so the site probably treats requests from Netlify's servers differently. Subscribing is unaffected.
- Old data files (pre-March 31) have fewer entries (~100/day vs 257) than current runs; only ~115 comics matched slugs under the old extraction approach.

## Environment & Setup
<!-- How to run this project. Critical for fresh agent sessions. -->

**Run locally:** `netlify dev` (full stack at `http://localhost:8888`) or `python run_app.py` (Flask at `http://localhost:5001`)
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) — 942 passing (the fetch-feed tests run the Netlify function under `node` and skip without it), requires Python ≥3.10 (on the host, bare `python3` is Apple's 3.9.6; build venvs from `/opt/homebrew/opt/python@3.14/bin/python3.14`, the production venv's base)
**Install (pipeline host):** `venv/bin/python -m pip install -r requirements.txt -c constraints.txt` — the constraints file pins transitives so the host venv is reproducible. CI's Tests job installs the same way (since #249); only the weekly `dependency-canary.yml` installs unconstrained. Change the host venv only after a PR merges, under `/usr/bin/lockf -k -t 1800 logs/pipeline.lock`
**Deploy:** Push to `main` to trigger Netlify deployment
**Key env vars:** `FLASK_DEBUG` (local optional), `NODE_VERSION`, `NETLIFY_FUNCTIONS_DIR`
**Production pipeline:** see [docs/LOCAL_AUTOMATION_README.md](LOCAL_AUTOMATION_README.md) and [docs/DEPLOYMENT.md](DEPLOYMENT.md)

## Architecture Notes
Python package (`comiccaster/`) provides the feed generator and scraper base classes. Source-specific scrapers and generators live in `scripts/`. Netlify serves `public/` as static files; `functions/` holds the OPML-generation and feed-preview serverless functions.

The daily pipeline is three phases, orchestrated by `scripts/local_master_update.sh`:

- **Phase 1 — scrape.** Each source has a dedicated scraper that writes `data/<source>_YYYY-MM-DD.json`.
- **Phase 2 — generate.** Each source has a dedicated generator that reads the latest JSON and writes `public/feeds/*.xml`. All generators are network-free. After the generators, `scripts/generate_catalog.py` rebuilds `public/catalog.json` from the comic lists and feed files (also in Pass 2 and in push recovery).
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

### 2026-10-24 (afternoon, orchestrated)
- **Goal:** The operator asked two things: should ComicCaster be rebuilt in Rust for security, and how could it be made friendlier to AI agents.
- **Accomplished:**
  - **Rust: no.** The code the public can reach is static files plus six Netlify functions in JavaScript. The Python only runs on the host. Today's real risks were logic, config and patching gaps, none of which memory safety prevents.
  - **#244:** `fetch-feed.js` had been an open proxy; it fetched Hacker News' feed for anyone who asked, verified live. It now allows only our feeds and exact listed external URLs, with no redirects. Buttersafe's `feed_url` moved to feedburner, because the old URL redirected there.
  - **#245 / #247:** The daily host audit found certifi 2026.7.22 affected by GHSA-6q48-6c7w-9gw2 (critical, compromised emSign CA keys). Pinned 2026.10.19. The host's pip went to 26.2.2 from a hash-pinned wheel, because pip uses its own bundled certifi alongside the installed one (PSF advisory, 2026-10-20). Removed APScheduler, tzlocal and requests-toolbelt. Audit: no known vulnerabilities in 46 packages.
  - **#246 / #248:** `catalog.json`, cross-origin headers, `llms.txt` and `robots.txt` for agents. Spanish feeds now declare `es`.
  - **#249:** CI tests the host's pinned versions. Two gaps explained why CI had been green while the host was vulnerable: CI installed unconstrained, and GitHub's dependency graph doesn't read `constraints.txt`.
  - **Orchestration:** two side sessions ran in worktrees, with each shared file split between them. Host venv changes ran only after merge, under the pipeline lock. Every report was re-verified before merging, and all branches and worktrees were cleaned up afterwards. See `docs/solutions/best-practices/parallel-sessions-on-the-live-pipeline-checkout.md`.
- **Open:** the first live runs on 2026-10-25 and the canary on Monday (What's Next #1), plus three operator decisions (Open Decisions).

### 2026-10-24
- **Goal:** Patch CVE-2026-111497 (Brotli decoder memory corruption, CVSS 9.2) on the pipeline host, working from the operator's vulnerability brief.
- **Accomplished:**
  - **#243:** `constraints.txt` `brotli==1.2.0` → `1.2.1`, and `requirements.txt` `brotli>=1.2.0` → `>=1.2.1`. No other pins changed. Built in a worktree, tested in a throwaway venv, merged once CI passed.
  - **Host venv:** `pip show brotli` went from 1.2.0 to 1.2.1. A `pip freeze` diff from before and after the install shows only that line changed. The suite passed 819 in the production venv, and again after Homebrew Node 26.8.1 → 26.12.1.
  - **Why the host was exposed while CI was green:** CI installs without `constraints.txt` and already resolved 1.2.1. The host lock is what kept 1.2.0. Added to `docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md`.
  - **Brief corrections:** bare `python3` on the host is 3.9.6 (too old for the repo), and Pass 1/2 never pull; they run `git reset --hard origin/main`, so stray edits in the pipeline clone are wiped, not rejected.
- **Repo security settings (operator call):** turned on Dependabot security-update PRs and secret-scanning push protection.
- **Not ComicCaster, handed off:** Homebrew's `node` uses Homebrew's shared libbrotli, and the long-running OpenClaw processes still had the old Node and brotli 1.2.0 loaded after the upgrade. That's for the OpenClaw/Homebrew owner. The ComicCaster pipeline and tests never use the host's Node.
