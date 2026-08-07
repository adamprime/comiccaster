---
title: Comics Kingdom auth fails on the first Chrome launch after an auto-update
date: 2026-08-07
category: logic-errors
module: scrapers
problem_type: environment
component: comicskingdom_scraper_individual.py / Chrome profile
severity: medium
applies_when:
  - "Comics Kingdom Pass 1 fails at is_authenticated but the same scrape works by hand hours later"
  - "A CK failure appears every few days with no pattern in the reauth calendar"
  - "The log shows an is_authenticated START line with no END line"
  - "A scrape failure 'fixed itself' and you are about to credit whatever you did last"
tags: [comicskingdom, chrome, auto-update, selenium, profile-migration, flaky, misdiagnosis]
stack: [selenium, chrome, macos]
github_issues: [183, 184]
---

## TL;DR

**The first CK Chrome launch after a Chrome auto-update fails, then self-heals
on the next run.** Chrome detects the version bump via `Last Version` in the
profile directory and migrates the profile on that launch; that launch is
unreliable. It is not a session problem and a reauth is not the fix.

Confirmed 2-for-2 against the install times:

| Chrome install | Next CK Pass 1 | Result |
| --- | --- | --- |
| `151.0.7922.75` — Aug 4 20:09 | Aug 5 03:12 | ❌ |
| — | Aug 5 09:34, Aug 6 03:29 | ✅ ✅ |
| `151.0.7922.76` — Aug 6 18:14 | Aug 7 03:13 | ❌ |
| — | manual probe Aug 7 07:40 | ✅ |

## Why it reads as two unrelated incidents

The symptom is not stable, which is most of the difficulty:

- **2026-08-05** — `driver.get` completed (15s) and landed on a login URL.
  Reads exactly like an expired session.
- **2026-08-07** — `driver.get` threw immediately. The log showed a START
  timing line, **no END line**, and nothing else.

Worse, `is_authenticated` caught the exception into `e` and never printed it,
and *both* paths printed `❌ Authentication failed - please run reauth script`.
On Aug 7 that was actively wrong advice.

## Diagnosis

Check Chrome's install time against the last good run before anything else:

```bash
ls -lT /Applications/Google\ Chrome.app/Contents/Frameworks/Google\ Chrome\ Framework.framework/Versions/*/
cat ~/.comicskingdom_chrome_profile/"Last Version"
```

If Chrome updated between the last success and the failure, this is that. To
confirm quickly, just run the scrape again — it should pass with no reauth.

## The fix

`scripts/comicskingdom_scraper_individual.py` retries authentication **once
with a fresh driver**:

```python
if not authenticate_with_cookies(...):
    driver.quit()
    driver = setup_driver(...)          # a NEW launch, not a re-navigation
    if not authenticate_with_cookies(...):
        return 1
```

Rebuilding the driver is the whole point. What recovers is the **next launch**,
once migration has completed — re-navigating inside the same session would not
have fixed either day. `is_authenticated` now also prints the real exception
and distinguishes "redirected to login" (reauth genuinely needed) from
"navigation failed" (retry).

## The general lesson

**A self-healing failure looks fixed by whatever you did last.** On Aug 5 the
conclusion was server-side session invalidation; the operator reauthed, the
next run succeeded, and that closed the investigation. Aug 7 recovered with no
reauth at all, which is what exposed the real trigger — the Aug 5 reauth was
probably unnecessary.

When a fix "works", check whether doing nothing would also have worked. Here
the tell was available and unused: the failure recurred on a cadence that
matched Chrome's release schedule, not the reauth calendar.

Related: `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`
(the same week's other lesson — a check asserting something it never observed).
