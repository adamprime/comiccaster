---
title: Merging a Dependabot bump does not update the host venv the pipeline runs from
date: 2026-08-24
category: best-practices
module: pipeline
problem_type: config-drift
component: requirements.txt / venv/ on the always-on host
severity: medium
applies_when:
  - "Dependabot PRs have been merged but scraper behavior on the host is unchanged"
  - "CI is green on a dependency bump yet the nightly run still hits an old library bug"
  - "Reproducing a pipeline failure locally gives a different result than the host does"
  - "Auditing what version of selenium/requests the production scrapers actually load"
tags: [dependencies, dependabot, venv, drift, selenium, pipeline, ci-vs-production]
stack: [python, github-actions]
github_prs: [163, 170, 182, 186, 189]
---

## TL;DR

`requirements.txt` is the *declared* dependency set. The daily pipeline executes
from `venv/` on the always-on host. Nothing connects the two automatically, so
merging a bump advances the declaration while production keeps running the old
library. Run `venv/bin/python -m pip install -r requirements.txt` on the host
after merging dependency PRs — it is the step that makes the bump real.

## What was observed

On 2026-08-24, five Dependabot PRs were open. Before merging, the host venv held:

| package      | venv had | requirements.txt pinned |
|--------------|----------|-------------------------|
| selenium     | 4.44.0   | 4.46.0                  |
| pytest       | 9.1.0    | 9.1.1                   |

The venv was **two selenium minors behind the pin that was already on `main`** —
drift accumulated from earlier merges, not from the PRs being reviewed that day.

## Why it is easy to miss

Every signal available in the PR says "shipped":

- CI installs `requirements.txt` fresh into a clean runner, so it always tests
  the *new* version and always goes green.
- Netlify redeploys on push, which makes the merge feel like a deployment.
- The nightly pipeline keeps reporting ALL SUCCESS, because it is succeeding —
  just with the old libraries.

None of those touch `venv/`. Netlify serves the static feeds; it does not run
the scrapers. The scrapers run on the host, from the venv, and only a manual
`pip install` moves that forward.

## The check

```bash
# What production actually loads, vs. what main declares:
venv/bin/python -m pip list | grep -iE "^(selenium|pytz|feedparser|python-dotenv|APScheduler|requests) "
cat requirements.txt
```

## The fix, and how to verify it

```bash
git pull --rebase                                  # get the merged pins
venv/bin/python -m pip install -r requirements.txt # make them real
venv/bin/python -m pytest -q                       # 491 passed
```

For a **selenium** bump specifically, `pytest` is necessary but *not* sufficient:
the suite mocks the browser by design (see CLAUDE.md — unit tests never touch
live sources), so it exercises none of the driver API that actually changed.
Smoke-test the real driver path before the next scheduled run:

```python
from selenium.webdriver.chrome.options import Options
from comiccaster.webdriver_setup import build_chrome_driver
o = Options()
for f in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage"):
    o.add_argument(f)
d = build_chrome_driver(o)
print(d.capabilities["browserVersion"], d.capabilities["chrome"]["chromedriverVersion"])
d.quit()
```

That confirms `webdriver_manager` still resolves a ChromeDriver matching the
installed Chrome under the new selenium — the exact failure mode from the
2026-06-09 incident documented in `comiccaster/webdriver_setup.py`.

Note that loading a GoComics URL in this smoke test returns an
"Establishing a secure connection" interstitial. That is the site's bot check
answering a bare headless browser, **not** a selenium regression — the
production GoComics path authenticates separately. Judge the smoke test on
whether the driver launches, reports versions, and quits cleanly.

## Timing

Do the sync in the window between runs, not just before one. Pass 1 is 03:05 and
Pass 2 is 13:00 (GoComics only). A late-morning sync leaves hours to notice a
problem; a 12:55 sync does not.

## Related

- `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md` — the
  other case where the pipeline reported success while doing nothing useful.
