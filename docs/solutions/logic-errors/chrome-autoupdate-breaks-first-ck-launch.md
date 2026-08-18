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

## Scope correction (2026-08-18): this covers Aug 7, not Aug 5

This document originally claimed **both** Aug 5 and Aug 7, on the strength of the
Chrome install times. Later evidence says Aug 5 belongs to the *other* CK failure
mode — the server-side session TTL:

- Aug 5's symptom was a clean **login redirect** (session rejected); Aug 7 threw
  on **navigation**. Different failures.
- Aug 5 fits the ~7-day server TTL exactly: reauth Jul 28 06:17 + 7d ≈ Aug 4,
  failed Aug 5 03:12. That reauth *was* the fix.
- Every session-type CK failure lands on a **Tue/Wed** (7 of 7), tracking the
  operator's Monday reauth. Aug 7 — a **Friday** — is the one that breaks the
  pattern, which is precisely why it has a different cause.

Treat the Chrome-update trigger as real but narrow: it explains a **navigation
error** on the first launch after an update. A login redirect is a session
problem. See `docs/solutions/logic-errors/comicskingdom-session-two-clocks.md`.

## The general lesson

**A self-healing failure looks fixed by whatever you did last — and so does a
correctly-fixed one.** Two symmetric errors happened here, a week apart:

1. Aug 5's reauth worked, and the investigation stopped there.
2. Aug 7 recovered *without* a reauth, and that was over-generalised backwards
   onto Aug 5, concluding the earlier reauth had been unnecessary. It hadn't.

The correction to both is the same: check whether the *symptom* matches the
mechanism before assuming one cause covers every occurrence. Two failures in the
same component days apart are not automatically the same bug — here the log line
distinguishing "redirected to login" from "navigation failed" is the whole tell,
which is why the fix that prints it was worth more than the retry beside it.

Related: `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`
(the same week's other lesson — a check asserting something it never observed).
