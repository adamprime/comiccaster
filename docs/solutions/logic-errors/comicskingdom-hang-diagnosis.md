# Comics Kingdom scraper hang — diagnosis

**Status:** First observation window complete. Findings captured. Unit 3 shape decided.

**Plan:** [docs/plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md](../../plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md) — Unit 1.

## TL;DR

The hang is a CK/WAF slow-walk on `driver.get("https://comicskingdom.com")` when the request arrives with no session cookies. `_individual` and `_secure` both exhibit it — it is a property of the "navigate to domain before injecting cookies" pattern, not a property of either scraper's extraction strategy. **Shape A (persistent Chrome profile, TinyView pattern)** is the right fix: a profile-based session arrives with session cookies already set, so the first request is recognized as authenticated and bypasses the slow-walk entirely.

## What was captured

Two instrumented runs on the Mini (user `openclaw`), 2026-04-18 afternoon:

| Run | Scraper | Invocation | Outcome |
|---|---|---|---|
| 1 | `_individual` | `python scripts/comicskingdom_scraper_individual.py --show-browser --date 2026-04-18 --output-dir data` at 14:09:09 | Success, 153/153 |
| 2 | `_secure` | `python scripts/comicskingdom_scraper_secure.py --show-browser --date 2026-04-18 --output-dir /tmp/ck_diag` at 14:24:33 | Domain-hit timed out; recovered; extracted 97 comics from favorites page |

Environment: Chrome 147.0.7727.101, macOS (Mini), cookies 0 days old (refreshed earlier that morning).

## Which call site hangs

Confirmed: **`driver.get("https://comicskingdom.com")` inside `load_cookies()`**. This is the navigation that must happen before `add_cookie` can set session cookies — so the request arrives at CK with no cookies, which is what triggers the WAF slow-walk.

Timings from the two runs:

| Call site | `_individual` (14:09) | `_secure` (14:24) |
|---|---|---|
| `webdriver.Chrome()` construction | 1.22s | 0.66s |
| **`driver.get(comicskingdom.com)` in `load_cookies`** | **20.39s** | **30.01s → TIMEOUT** |
| `add_cookie` loop (153 cookies) | 0.15s | 0.14s (failed, driver in bad state) |
| `driver.get(/favorites)` in `is_authenticated` | 2.65s | 2.85s |
| `driver.get(/favorites)` in `extract_favorites` | n/a | 0.51s |

The 30s figure in Run 2 matches the observed overnight-failure fingerprint exactly (`Timed out receiving message from renderer: 29.xxx`). Same call site, same renderer-timeout class, captured in real-time 15 minutes after a nearly-successful run on the same host.

Subsequent navigations after cookies are loaded (the `is_authenticated` and `extract_favorites` calls) are fast (~0.5–3s) in both runs, consistent with the WAF treating authenticated requests normally.

## Does `_secure` hang in the same place?

Yes. `_secure` reproduced the failure mode exactly — same call site, same timeout class, same 30s fingerprint. This rules out any "switching production scraper fixes it" path. The slow-walk is a property of the cookie-load *pattern* (`driver.get(domain) → sleep → add_cookie`), not of either scraper's identity.

Important secondary finding: after the 30s timeout, Chrome retained enough session state that the next navigation (`is_authenticated`'s hit to `/favorites`) succeeded cleanly in 2.85s. The WAF is not blocking — it is serving slowly on unauthenticated requests to the root domain. Once *any* state is in the browser, subsequent requests are normal.

## Why a persistent Chrome profile sidesteps this

The pickled-cookie flow requires a `driver.get(domain)` before Selenium will accept `add_cookie` calls (Selenium requires the browser to be on the target domain to set its cookies). That first `driver.get` is always an unauthenticated request, and that is what gets slow-walked.

A `--user-data-dir` Chrome profile has no such requirement. Chrome starts with the session cookies already present in its storage. The *first* network request to CK arrives carrying a valid session — same as a returning user visiting the site in a browser — and the WAF routes it through the normal path.

This is exactly why TinyView (profile-based) has shown zero comparable failures in the same log window. The architectural asymmetry with CK (pickled cookies) is the operational asymmetry.

## Unit 3 shape recommendation

**Shape A (persistent Chrome profile).** The data rules out Shape B (consolidate on `_secure`) — `_secure` has the same failure. Shape C (Chrome version pin) is unlikely — same Chrome version produced both 20s and 30s+ timings in a 15-minute window, which is server-side variance, not client instability.

Scope of Shape A implementation:
- Extend `setup_driver` in `_individual` to accept `use_profile=True`; add `--user-data-dir=~/.comicskingdom_chrome_profile`.
- Profile directory mode `0o700` on creation (security review finding).
- When `use_profile=True`, skip `load_cookies`'s `driver.get + sleep + add_cookie` sequence entirely; go directly to `is_authenticated`.
- Add an in-code empty-profile check that emits a distinct "profile not seeded, run reauth" message — not "please run reauth script" — so deploy-day confusion doesn't reproduce the exact misdiagnosis this plan is trying to eliminate.
- Rewrite `reauth_comicskingdom.py` to seed the profile instead of saving pickled cookies. Note: `reauth_comicskingdom.py` currently imports `login_with_manual_recaptcha` from `_secure`; either port that helper into `_individual` (preferred) or keep `_secure` in a minimal maintenance mode pending its deletion.
- Credentials (`COMICSKINGDOM_USERNAME` / `COMICSKINGDOM_PASSWORD`) only needed by the reauth path after migration, not by the daily scrape path.

## `_individual` vs `_secure` recommendation

**Keep `_individual` as the production scraper. Deprecate `_secure` after Shape A stabilizes.**

Additional evidence from Run 2: `_secure` extracted only 97 of 153 comics on a successful run. The favorites page shows ~98 items even with its built-in "Load more" clicks (3 click iterations in the run). `_individual`'s per-URL approach gets the full 153 because it doesn't depend on the favorites page's pagination behavior.

The 2026-04-09 favorites-page rewrite did real reliability work (popup dismissal, lazy-image handling, diagnostic snapshots), but those benefits belong with the scraper that actually runs. After Shape A lands on `_individual`:

1. Port popup dismissal helper from `_secure` into `_individual` (separate follow-up plan).
2. Port `_save_diagnostic_snapshot` into `_individual` (same plan).
3. Delete `_secure` once `reauth_comicskingdom.py` and `scripts/diagnose_ck_page.py` no longer import from it.

## What to do with the instrumentation itself

Leave instrumentation in place on both `_individual` and `_secure` until Shape A lands and has proven itself over a week of successful overnight runs. The timestamped markers are the fastest way to confirm the fix is working (specifically: the `load_cookies: driver.get(comicskingdom.com)` START/END pair should disappear entirely from the log after Shape A, because that code path will not run when `use_profile=True`).

Once `_secure` is deleted in the post-Shape-A cleanup, its instrumentation goes with it. The `_individual` instrumentation can be removed (or kept as permanent observability — a judgment call at that point).
