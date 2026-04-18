# Comics Kingdom scraper hang — diagnosis

**Status:** Observation pending. This document will be filled in after 2–3 overnight runs of the instrumented scraper, and the manual `_secure` comparison runs.

**Plan:** [docs/plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md](../../plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md) — Unit 1.

## What was captured

<!-- After observation:
 - Date range of observation
 - Number of overnight runs captured
 - Number of hang events captured
 - Relevant environment details (Chrome version, ChromeDriver version, macOS version)
 - Manual _secure runs: dates, outcomes
-->

_To be filled in._

## Which call site hangs

<!-- After observation, name the specific call site(s) that produced the 29.x s timeout.
Quote the relevant log lines with timestamps. Examples of what the answer might look like:

  - "Hang fires on load_cookies: driver.get(comicskingdom.com) — START at 03:05:02.412, no END line appears; next line is the 29.931s Selenium error at 03:05:32.343."
  - "Hang fires on is_authenticated: driver.get(/favorites) — START at 03:07:14.001, END at 03:07:44.015 (30s); the cookie-load driver.get completed normally in 1.2s."
  - "Hang fires on scrape_comic_page[1]: driver.get — after cookie load and is_authenticated both completed normally."
-->

_To be filled in._

## Does `_secure` hang in the same place?

<!-- After manual _secure runs:
  - Same hang: both scrapers exhibit the same timeout fingerprint on the same/analogous call site
  - Different hang: _secure hangs elsewhere (e.g., on the favorites-page load specifically)
  - No hang in _secure window observed: _secure ran cleanly across N attempts
  - Note that a 2-run manual window may not reproduce a ~weekly failure; state confidence accordingly.
-->

_To be filled in._

## Unit 3 shape recommendation

<!-- Pick one of the plan's Unit 3 shapes (A/B/C) or propose a hybrid.
Justify with the captured data.

  Shape A (profile-based session): triggered if the hang is specifically on
    the cookie-injection sequence; i.e. _secure does not hang under the same
    conditions that trip _individual.

  Shape B (consolidate on _secure): triggered if _secure does not hang in the
    failure conditions that trip _individual and its favorites-page strategy
    looks robust against current CK markup.

  Shape C (Chrome/ChromeDriver version pin): triggered if the hang is
    intermittent across both scrapers and correlates with ChromeDriver version
    rather than any code path.

  Hybrid: specify the combination and why.
-->

_To be filled in._

## `_individual` vs `_secure` recommendation

<!-- Independent of Unit 3's shape:
  - Keep both (reauth and diagnose still import from _secure, _individual stays in master script)
  - Consolidate on _secure, deprecate _individual (follows if Shape B)
  - Consolidate on _individual, port login helper from _secure, deprecate _secure
  - Merge into one scraper (describe what that looks like)

Justify with data from Unit 1's runs and the coupling graph.
-->

_To be filled in._

## What to do with the instrumentation itself

<!-- After Unit 3 lands, the instrumentation helper and log lines should be
removed unless they earned permanent status (e.g., they caught something
during Unit 3's validation that would have been missed otherwise).
-->

_To be filled in._
