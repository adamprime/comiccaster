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
  - "A CVE is fixed upstream and CI already tests the fixed version, but the host may still run the vulnerable one"
tags: [dependencies, dependabot, venv, drift, selenium, pipeline, ci-vs-production, constraints, security, brotli]
stack: [python, github-actions]
github_prs: [163, 170, 182, 186, 189, 243]
last_updated: 2026-10-24
---

## TL;DR

`requirements.txt` is the *declared* dependency set. The daily pipeline executes
from `venv/` on the always-on host. Nothing connects the two automatically, so
merging a bump advances the declaration while production keeps running the old
library. Run `venv/bin/python -m pip install -r requirements.txt -c constraints.txt`
on the host after merging dependency PRs. It is the step that makes the bump
real. Since 2026-08-25, `constraints.txt` locks every transitive on the host, so
a fix only reaches production once it is in **that** file. CI never reads it.
That's how the host was still on the vulnerable brotli 1.2.0 while CI tested
1.2.1 (see "Security fixes" below).

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
git pull --ff-only                                 # get the merged pins (tree must be clean)
venv/bin/python -m pip freeze > /tmp/before.txt
venv/bin/python -m pip install -r requirements.txt -c constraints.txt   # make them real
venv/bin/python -m pip freeze | diff /tmp/before.txt -                  # only the bumped lines should move
venv/bin/python -m pytest -q                       # 819 passed on 2026-10-24
```

Run it in the pipeline clone only on a clean tree. Pass 1 and Pass 2 begin
with `git reset --hard origin/main`, so a half-finished edit there is silently
wiped at 03:05 or 13:00 rather than blocking the run. Build any change in a
`git worktree`, and test it in a throwaway venv made from the production venv's
base interpreter (`/opt/homebrew/opt/python@3.14/bin/python3.14`). Bare
`python3` on the host is Apple's 3.9.6, which `setup.py` rejects.

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

## Security fixes: the lock holds them back too (2026-10-24)

`constraints.txt` made the host reproducible, which also means a transitive
security fix never arrives on its own. CVE-2026-111497 (Brotli decoder memory
corruption, CVSS 9.2) was fixed in PyPI `Brotli` 1.2.1 on 2026-10-22. Two days
later:

| where | brotli | why |
|---|---|---|
| CI | 1.2.1 | installs `requirements.txt` unconstrained; `>=1.2.0` resolved the newest |
| host venv | 1.2.0 | `constraints.txt` pinned `brotli==1.2.0` |

Every PR stayed green, and the pipeline kept reporting ALL SUCCESS, on the
vulnerable version. The "CI is the canary" design is working as intended
here: CI showed 1.2.1 broke nothing. But that only helps if someone then moves
the lock.

**The `Accept-Encoding` header doesn't protect us.** `comiccaster/http_client.py`
sends `Accept-Encoding: gzip, deflate`, but urllib3 picks its decoder from the
*response's* `Content-Encoding` (`urllib3/response.py`, `CONTENT_DECODERS`) and
includes `br` whenever brotli is importable. Any site a scraper fetches could
send a `br` body, and that's how a compromised comic site reaches the decoder.

**The fix (#243)** bumped both files: `constraints.txt` to `brotli==1.2.1`
(what the host installs) and `requirements.txt` to `brotli>=1.2.1` (so an
unconstrained install can't resolve the vulnerable version). Then run the
install and verification above. The freeze diff should show only the brotli
line.

**Why nothing proposed it sooner:** Dependabot version updates run weekly
(they do edit `constraints.txt`; see pluggy, #241), and Dependabot
security-update PRs were turned off. **They were turned on on 2026-10-24**, so
the next transitive CVE should arrive as a PR as soon as GitHub publishes an
advisory. That PR is still only half the fix. Merging it changes the files,
and the host only changes when you run the install above.

## Timing

Do the sync in the window between runs, not just before one. Pass 1 is 03:05,
the Far Side morning pass runs every 30 minutes from 03:30 to 12:00 (from the
same venv), and Pass 2 is 13:00 (GoComics only). So the open window is from
when Pass 2 finishes until about 02:45. First check that nothing is running
(`launchctl list | grep -i comiccaster`; a PID in the first column means a run
is in progress). An afternoon or evening sync leaves hours to notice a problem
before Pass 1; a 02:55 sync does not.

## Related

- `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md` — the
  other case where the pipeline reported success while doing nothing useful.
