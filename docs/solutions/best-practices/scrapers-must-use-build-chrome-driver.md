---
title: Every Selenium scraper must build its driver via build_chrome_driver
date: 2026-07-20
category: best-practices
module: webdriver
problem_type: best_practice
component: scrapers
severity: high
applies_when:
  - "A scraper builds a driver with raw webdriver.Chrome() instead of the shared helper"
  - "A 'chromedriver ... might not be compatible with the detected chrome version' warning appears"
  - "A scrape silently produces no data for a day or two after Chrome auto-updates"
  - "Adding a new Selenium-based comic source"
tags:
  - webdriver
  - chromedriver
  - selenium
  - webdriver-manager
  - tinyview
  - scraper-reliability
---

## TL;DR

All production Selenium scrapers must instantiate their driver through
`comiccaster.webdriver_setup.build_chrome_driver(options)`, which uses
`webdriver_manager` to download a ChromeDriver matched to the installed
Chrome on demand. A raw `webdriver.Chrome(options=options)` falls back to
whatever `chromedriver` sits on `PATH`, which drifts out of sync every time
Chrome auto-updates and silently breaks the scrape (incident 2026-06-09:
Chrome 149 vs ChromeDriver 147 took down Comics Kingdom, TinyView, and Far
Side until the binary was swapped by hand).

## The trap we hit twice

The 2026-06-09 migration moved most scrapers onto `build_chrome_driver`, but
`scripts/tinyview_scraper_secure.py` was missed. It kept a raw
`webdriver.Chrome()`. That function is not just the reauth path — the nightly
pipeline's `tinyview_scraper_local_authenticated.py` **imports `setup_driver`
from it**, so the one raw constructor was the driver source for the entire
TinyView pipeline.

On 2026-07-20 this surfaced as:

- A reauth warning: `chromedriver 149.0.7827.55 detected in PATH ... might
  not be compatible with the detected chrome version (150.0.7871.125)`.
- A silent 2-day data gap (`data/tinyview_*.json` stopped at Jul 18) — the
  scrape had been limping/failing while the session ALSO lapsed.

The fix was one line plus an import, routing `setup_driver` through
`build_chrome_driver`. Verified end-to-end: `webdriver_manager` auto-resolved
`~/.wdm/drivers/chromedriver/mac-arm64/150.0.7871.124/chromedriver` to match
Chrome 150, bypassing the stale PATH binary entirely, and the rescrape
recovered the gap.

## Do / don't

- **Do** build every driver with `build_chrome_driver(options)`. Grep guard:
  `grep -rln "webdriver.Chrome(" scripts/ comiccaster/` should return only
  non-production tooling (e.g. `diagnose_political_favorites.py`).
- **Do** add a guard test when touching a scraper's driver setup — e.g.
  `tests/test_tinyview_scraper_secure.py::TestSetupDriverBuilder` asserts
  `setup_driver` calls the shared helper, not a raw driver.
- **Don't** rely on `brew upgrade chromedriver`. It is a band-aid, the formula
  is now deprecated, and it can leave PATH *ahead* of Chrome (upgrade gave
  151 while Chrome was 150). The helper makes the PATH driver irrelevant for
  production scrapers.
- **Don't** trust "reauth succeeded" alone after a gap — confirm the dated
  JSON actually lands (`data/tinyview_$DATE.json`), which is what the pipeline
  invariant guard checks.

## Adjacent gotchas noted the same day

- TinyView's reauth prints `⚠️ No Firebase auth keys found` on every
  successful login — it is a cosmetic heuristic (session persists via cookies,
  not localStorage), not a failure signal.
- `chromedriver --version` on the freshly `brew`-installed binary hangs on
  this box even after clearing the Gatekeeper quarantine. Another reason not
  to depend on the PATH driver.

## Related

- Incident origin: `comiccaster/webdriver_setup.py` module docstring.
- `docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md` — the
  persistent-profile (Shape A) pattern that TinyView already uses for auth.
