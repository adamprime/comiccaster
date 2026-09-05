---
title: GoComics' Bunny Shield refuses HeadlessChrome — every favorites page came back as a challenge interstitial
date: 2026-09-05
category: logic-errors
module: scrapers
problem_type: external-site-change
component: authenticated_scraper_secure.py / comiccaster/webdriver_setup.py
severity: high
applies_when:
  - "GoComics scrape logs 'Login successful' then 'No comic containers found' on every custom page"
  - "/tmp/gocomics_debug_<date>.html is titled 'Establishing a secure connection ...'"
  - "A curl of any gocomics.com strip page returns HTTP 403 with 'cdn-challenge: true'"
  - "Any other source starts returning a bunny.net / '.bunny-shield' interstitial"
tags: [gocomics, bot-challenge, bunny-shield, headless, user-agent, selenium, webdriver_setup]
stack: [python, selenium]
github_issues: [198]
---

## TL;DR

Between the 2026-09-04 13:00 Pass 2 and the 2026-09-05 03:05 Pass 1, GoComics put
a **Bunny Shield** (bunny.net CDN) bot challenge in front of its strip and profile
pages. The challenge is a JavaScript proof-of-work interstitial titled
*"Establishing a secure connection ..."*. It **never clears for a browser whose
user-agent contains `HeadlessChrome/`**; the identical browser presenting
`Chrome/<same version>` clears it in under two seconds.

The fix lives in the shared driver builder: `build_chrome_driver()` now reads the
session's user-agent and, if it carries the headless token, overrides it via
Chrome DevTools (`Network.setUserAgentOverride`) with the same string minus
`Headless`. Real version kept, nothing else touched, headed sessions untouched.

## What the failure looked like

```
[1/7] Scraping GoComics (authenticated)...
✅ Login successful
Scraping: https://www.gocomics.com/profile/User52732/comics/221821
  ⚠️  No comic containers found. Page source saved to /tmp/gocomics_debug_2026-09-05.html
  Extracted 0 comics
  ... (same for all six pages)
✅ SUCCESS! Extracted 0 comics for 2026-09-05
```

The scraper's own exit was success. The invariant guard's *count* half caught it
(`GoComics: only 0 entries, expected at least 100`) and opened issue #198 — the
existence-only guard of before 2026-08-05 would have shipped an empty day as
ALL SUCCESS (see `silent-empty-scrape-passed-as-success.md`). Published feeds
were not damaged; the generator kept history and simply added nothing.

Login succeeded because the OAuth flow runs on Microsoft's B2C domain, which is
not behind the shield. Only `www.gocomics.com` pages are gated — and the homepage
is not, which is why a quick "is GoComics up?" check would have said yes.

## How it was diagnosed

1. `/tmp/gocomics_debug_2026-09-05.html` was 2 KB of challenge page, not a
   profile page: `<title>Establishing a secure connection ...</title>`, assets
   under `/.bunny-shield/`, an iframe on `shield-templates-prod.b-cdn.net`, a
   footer stuck at `Submitting...`.
2. `curl -I https://www.gocomics.com/garfield` → `403`, `server: BunnyCDN`,
   `cdn-challenge: true`. So it is the CDN, not a page-structure change.
3. A probe with the scraper's exact Chrome options, polling `driver.title`:

   | Mode | User-agent | Result |
   |---|---|---|
   | `--headless=new` | `HeadlessChrome/152` (default) | stuck at "Submitting..." for 90 s |
   | headed | `Chrome/152`, `navigator.webdriver` still `true` | clears in 1.7 s |
   | `--headless=new` + UA override | `Chrome/152` | clears in 1.7 s |

   Headed passing *with* the webdriver flag set is the key measurement: the shield
   was keying on the literal `HeadlessChrome` token, nothing more.
4. Ran the real scraper against a scratch `--output-dir` with the fix: 231 comics
   across all six pages.

## The fix

`comiccaster/webdriver_setup.py`:

- `regular_chrome_user_agent(ua)` — drops `HeadlessChrome/` → `Chrome/`, keeps the
  version.
- `build_chrome_driver()` calls `_present_as_regular_chrome(driver)` after
  construction. It reads `navigator.userAgent`; if the token is present it
  applies `Network.setUserAgentOverride` for the session. The override persists
  across navigations. A failure is logged as a warning, never raised — most
  sources do not care and the scrape should still run.

Because every scraper goes through `build_chrome_driver` (see
`best-practices/scrapers-must-use-build-chrome-driver.md`), Comics Kingdom,
TinyView and Far Side get the same treatment for free if their CDNs follow suit.

`scripts/authenticated_scraper_secure.py`:

- `is_bot_challenge_page(html)` recognises the interstitial, and the
  "No comic containers found" branch now says so explicitly and points here.
  The old message is kept so existing log greps still work.

Why a DevTools override rather than `--user-agent=...` on the command line: the
flag needs the Chrome version *before* launch (and the version bumps itself —
see `chrome-autoupdate-breaks-first-ck-launch.md`). Reading the browser's own
string after launch and editing one token is always accurate.

## If it happens again

- **Same symptom, headless still refused after this fix:** Bunny has tightened
  detection beyond the UA token. Run the GoComics scraper headed
  (`--show-browser`) — the measured fallback, and the host already has a GUI
  login and runs Comics Kingdom headed via `CK_SCRAPER_EXTRA_ARGS`. Re-measure
  before assuming; the probe is three navigations.
- **Different source, same interstitial:** the fix is already in the shared
  builder. Check that scraper actually uses `build_chrome_driver`.
- **Recovery:** land the fix before the next pass. Pass 2 (13:00) runs
  `--merge` and fills the day's file; its success dispatch closes the issue.
  No manual feed surgery needed.
