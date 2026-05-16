# Project Status
<!-- Updated: 2026-05-16 by Codex -->

## Project Overview
ComicCaster aggregates comics from GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, and first-party external RSS feeds into standards-compliant RSS feeds and OPML bundles. A Python pipeline handles scraping and feed generation where ComicCaster owns the feed; external RSS entries link directly to publisher-provided feeds. Netlify serves the static site and feed files.

## Current State
Stable. Shape A (CK profile-based auth) has been on prod since 2026-04-20 with no observed regressions; daily runs report all-success on most days, with the expected weekly CK session refresh handled manually via `reauth_comicskingdom.py`. PR #139 is open from `codex/external-rss-catalog` to add a separate External RSS catalog and OPML flow for first-party publisher feeds. It avoids the scrape/generate pipeline entirely and should be validated through CI plus the Netlify preview before merge.

**Phase:** Maintenance (active)
**Last Session:** 2026-05-16
**Last Session Summary:** PR #139 opened from `codex/external-rss-catalog`: added a first-party External RSS catalog with its own browse and OPML tabs, direct `feed_url` handling in `functions/generate-opml.js`, Netlify function packaging for the new catalog, docs updates, and 5 new catalog/UI tests. Full local suite: 281 tests passing. Direct OPML smoke check verified xkcd and Poorly Drawn Lines use publisher RSS URLs rather than ComicCaster-generated URLs.

## What's Working
<!-- Features/systems that are shipped and stable. Keep this current. -->

- Daily multi-source RSS feed generation and publishing workflow
- All six sources use a uniform scrape-to-data / generate-from-data architecture (`scripts/scrape_*.py` → `data/<src>_$DATE.json` → `scripts/generate_*.py` → `public/feeds/*.xml`)
- Production entrypoint is tracked in git (`scripts/mini_master_update.sh`) — no more untracked wrappers patching the master script at runtime
- Push-conflict recovery uses save / fetch / reset / regenerate (no `git pull --rebase` against generated XMLs)
- Invariant guard between Phase 2 and Phase 3 catches silent scrape regressions (scrape reports success but its dated JSON is missing)
- Comics Kingdom authentication uses a persistent Chrome profile at `~/.comicskingdom_chrome_profile` (Shape A); `reauth_comicskingdom.py` is the operator entry point for refresh
- Chrome boundary instrumentation in `_individual` — timestamped log lines at every `driver.get` make hang-site localization a grep
- 281-test suite passing locally on the external RSS branch; mainline CI covers Python 3.10 / 3.11 / 3.12
- 312 GoComics feeds, ~153 Comics Kingdom feeds, TinyView feeds, Far Side Daily Dose + New Stuff, New Yorker Daily Cartoon, and 10 Creators feeds updating daily
- Static site + Netlify functions deployment flow
- Security policy and private vulnerability reporting enabled; **zero open CodeQL alerts**
- Consistent comic strip sizing (max-width: 700px) and centering across all sources (#105)
- Manual backfill script available for GoComics feed recovery (`scripts/backfill_gocomics_feeds.py`)
- Daily automated feed monitoring via agent
- Public feedback site (https://feedback.comiccaster.xyz) auto-tracked: a daily GitHub Action opens an issue for each new post (`feedback-site` label)
- GitHub Actions on Node 24 actions runtime; only 4 active workflows in `.github/workflows/` (down from 8)

## What's In Progress
<!-- Active work items. Update every session. -->

| Item | Status | Branch | Notes |
|------|--------|--------|-------|
| External RSS catalog | PR open | `codex/external-rss-catalog` | PR #139 adds a separate External RSS tab and OPML path for first-party feeds; merge after CI and Netlify preview review. |

## What's Next
<!-- Prioritized backlog. Top item = next thing to work on. -->

1. **Review and merge PR #139** — confirm CI and Netlify preview. Preview checks: External RSS tabs render, search works, Poorly Drawn Lines shows `https://poorlydrawnlines.com/feed/`, and External OPML contains publisher feed URLs.
2. **`chmod 700` on `~/.tinyview_chrome_profile`** — same security fix that Shape A applied to the CK profile. Pre-existing issue with TinyView's `setup_driver`.
3. **Audit `SETUP_TINYVIEW_AUTH.sh`** — script is operationally correct (calls `tinyview_scraper_secure.py`, which is the canonical interactive auth tool there). Worth re-reading against the same operator-pragmatic principle the CK setup-doc cleanup applied.
4. **Generalize entry-count invariant across sources** — deferred from the original CK reliability plan. Useful across GoComics, TinyView, Creators, etc. Revisit only if partial-scrape incidents become observed.
5. **Investigate issue #91** (GoComics strips don't save to read-later platforms).
6. **Optional source-code-comment cleanup pass** — several files have docstrings and comments that could be trimmed for accuracy and conciseness. Deferred: low risk, real cost.

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
**Run tests:** `pytest -v` (or `pytest -v --cov=comiccaster --cov-report=term-missing`) — 281 passing on `codex/external-rss-catalog`, requires Python ≥3.10
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

### 2026-05-16
- **Goal:** Add a cheap expansion path for popular webcomics that already publish first-party RSS feeds, without creating new scrapers or generated feed files.
- **Accomplished:**
  - Confirmed `main` was clean and current with `origin/main` before starting, then researched first-party RSS candidates.
  - Added `public/external_comics_list.json` with 25 non-mature external feeds. Included direct feeds even when a comic also exists in the GoComics catalog, because publisher feeds can update more frequently.
  - Excluded mature feeds for now; Oglaf was deliberately left out.
  - Added a dedicated External RSS browse tab and External RSS OPML tab in `public/index.html`, following the existing tab/table/list UI patterns.
  - Updated `functions/generate-opml.js` so `external-rss` entries preserve their publisher `feed_url` in OPML instead of being rewritten to ComicCaster `/rss/` or `/feeds/` URLs.
  - Updated `netlify.toml` to package the external, Spanish, and TinyView catalog JSON files with Netlify functions.
  - Updated README and the testing guide for the new catalog type.
  - Opened PR #139: `codex/external-rss-catalog` → `main`.
- **Validation:**
  - `pytest -q`: 281 passing.
  - External OPML smoke check verified xkcd and Poorly Drawn Lines output direct publisher feed URLs.
  - Static page smoke check verified External RSS tab markup, `external_comics_list.json` serving, and inline script parsing.
- **Didn't finish:** PR #139 still needs CI/Netlify preview review and merge.
- **Discovered:**
  - Questionable Content and Girl Genius did not have a clearly working official RSS URL from the obvious/current endpoints checked, so they were not added.
  - Some comics already present through GoComics, such as Poorly Drawn Lines and SMBC, have direct feeds that are worth listing separately.

### 2026-05-05
- **Goal:** Project review + opportunistic cleanup of accumulated tech debt.
- **Accomplished:**
  - PR #121: pytz 2026.1.post1 → 2026.2 (Dependabot, IANA tzdata bump).
  - PR #122: new GitHub Action (`watch-feedback.yml`) that polls the public feedback Atom feed daily and opens an issue for each new post. State lives in the issues themselves (label `feedback-site` + a `Source:` line in each body), so no state file is needed; idempotent.
  - PR #128: bumped active workflows to Node 24-supported actions (`checkout@v5`, `setup-python@v6`, `github-script@v8`) ahead of the 2026-06-02 deprecation. Pruned four dead/legacy workflows (`update-feeds-smart.yml`, `validate-feeds.yml`, `test-authenticated-scraping.yml`, `test-comicskingdom.yml`); 8 → 4 workflows.
  - PR #129 / #130: cleared CodeQL alerts #53 and #54 (`py/clear-text-logging-sensitive-data`, severity high). #129 first split `load_config_from_env` to return cookie-file and credentials separately; CodeQL still propagated the taint through tuple-unpacking, so #130 went further and dropped credential loading from `_individual.py` entirely (nothing in the post-Shape-A codebase still consumed it). Two real high-severity alerts → zero open alerts.
  - PR #131: deleted seven stale pre-Shape-A setup docs (`COMICSKINGDOM_SETUP.md`, `GITHUB_SECRETS_COMICSKINGDOM.md`, `DROPLET_QUICKSTART.md`, `DROPLET_SETUP.md`, `COMICSKINGDOM_FAVORITES_SETUP.md`, `TINYVIEW_AUTH_SETUP.md`, `NOTIFICATION_SETUP.md`) and one stale shell helper (`SETUP_COMICSKINGDOM_AUTH.sh`). `docs/setup/` removed entirely. Rewrote the `Credentials` section of `LOCAL_AUTOMATION_README.md` to reflect Shape A reality. −1684 / +6 lines.
  - PR #132: retired `scripts/comicskingdom_scraper_secure.py` (off the active path since 2025-11-15) and `scripts/diagnose_ck_page.py` (premise obsolete; also fixed a broken-import bug introduced in #130). Renamed `_individual.login_with_manual_recaptcha` → `wait_for_manual_login` to match what the function actually does. −908 / +20 lines.
- **Validation:**
  - 276 tests passing across all PRs.
  - All CI checks green on each PR (Python 3.10 / 3.11 / 3.12, CodeQL, Netlify deploy preview, redirect/header rules).
  - Zero open CodeQL alerts.
- **Didn't finish:** TinyView profile `chmod 700`, `SETUP_TINYVIEW_AUTH.sh` audit, optional source-code-comment cleanup pass — all queued in `What's Next`.
- **Discovered:**
  - `data/comicskingdom_cookies.pkl` is no longer git-tracked (handled in a prior session). The 2026-04-20 What's Next item to remove it is moot.
  - `tinyview_scraper_secure.py` is shared infrastructure, not legacy — imported by the active daily scraper (`tinyview_scraper_local_authenticated.py`) and the canonical entry point for first-time interactive setup. Earlier framing as "wrong scraper file" was incorrect; `SETUP_TINYVIEW_AUTH.sh` is operationally correct.

### 2026-04-20
- **Goal:** Review Dependabot PR #119 (uuid 13→14 in `functions/`); see if there's anything else worth cleaning up while in there.
- **Accomplished:**
  - Diagnosed #119: the `uuid` dep was orphaned — added for `functions/generate-token.js`, which was removed in commit `6fe3dd1ec` ("Replace token-based OPML generation with direct OPML generation without tokens"). No current JS file imports it.
  - Shipped `3fe2a54fa` direct-to-main: removed the dep entirely via `npm uninstall uuid`. Smoke-tested locally via `netlify dev` (generate-opml 200 + valid OPML, fetch-feed 405 method guard). Closed #119 with reference to the cleanup commit.
  - Noticed 41 additional files in `functions/node_modules/` tracked in git, grandfathered before the root `.gitignore` `node_modules/` rule. Confirmed no other grandfathered `node_modules/` directories in the repo.
  - Shipped PR #120 (`chore/untrack-functions-node_modules` → `727a7b177` squash-merge): `git rm -r --cached functions/node_modules`, −10,566 lines. Deploy preview verified Netlify installs from `functions/package-lock.json` at build time via `node_bundler = "esbuild"`. Post-merge prod smoke-tested green on `comiccaster.xyz`.
  - Removed the dead JS-fill block from `_individual.login_with_manual_recaptcha` (3× `execute_script` pairs that were always rejected by CK's bot check, forcing the operator to clear + retype every reauth). Dropped `username`/`password` params since they were theater. Rewrote the login banner to describe the real manual-type-and-click flow (no reCAPTCHA checkbox, invisible reCAPTCHA v3). Simplified `reauth_comicskingdom.py`: dropped `load_config_from_env` import + credential loading, updated intro blurb. Updated tests: deleted `test_signature_matches_secure` (drift from `_secure` is intentional; `_secure` dies 2026-04-25), updated three direct-call tests, added `test_does_not_inject_credentials_via_js`, updated reauth-main assertion, cleaned up now-unused setenv calls.
- **Validation:**
  - #120 deploy preview: generate-opml 200, fetch-feed 405.
  - Post-merge prod: generate-opml 200, fetch-feed 405.
  - Python test suite green on all 3 versions (3.10/3.11/3.12) for #120.
  - Local full suite: 276 tests passing after the JS-fill removal.
- **Didn't finish:** Real-world validation of the new reauth prompts happens Monday (next CK session expiry) on the prod host.
- **Discovered:** Netlify's `esbuild` bundler does install from `functions/package-lock.json` at deploy time — the 2023-era committed `node_modules/` was dead weight, not load-bearing.

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
