---
title: Comics Kingdom reauth silently minted no new token
date: 2026-07-28
category: logic-errors
module: comicskingdom
problem_type: bug
component: scripts/reauth_comicskingdom.py
severity: high
applies_when:
  - "Comics Kingdom auth fails the morning after a reauth that appeared to work"
  - "Pass 1 logs 'Authentication failed - please run reauth script' and only comicskingdom_$DATE.json is missing"
  - "Reasoning about how long a Comics Kingdom session lasts, or when to reauth"
  - "Adding a source whose credentials live in a persistent browser profile"
tags: [comicskingdom, authentication, session-token, cookie-expiry, reauth, chrome-profile, silent-failure, postcondition-verification]
stack: [python, selenium, chrome, sqlite]
github_prs: [179]
---

# Comics Kingdom reauth can silently no-op — verify the token expiry, not the browser

## Problem

The weekly Comics Kingdom re-authentication ran on Monday 2026-07-27, the browser
showed a logged-in page, and the operator considered it done — but no new session
token was written to the Chrome profile. The next morning's Pass 1 run failed
authentication and produced no `data/comicskingdom_2026-07-28.json`, so 153 CK
comics were missing from that day's feeds until a manual recovery scrape.

## Symptoms

- Pass 1 log, 2026-07-28 03:06, immediately after the auth probe:

  ```
  [03:06:54.939] is_authenticated: driver.get(/favorites) START
  [03:06:58.049] is_authenticated: driver.get(/favorites) END
  ❌ Authentication failed - please run reauth script
  ❌ Authentication failed
  ❌ Comics Kingdom scraping failed
  ```

  That message comes from the profile branch of `authenticate_with_cookies`
  (`scripts/comicskingdom_scraper_individual.py:189`), reached because
  `is_authenticated` navigated to `/favorites` and was redirected to a URL
  containing `login`.
- Exactly one missing artifact: `data/comicskingdom_2026-07-28.json`. The other
  six sources succeeded, so this surfaced as a single-source gap, not a broken run.
- The reauth the night before gave no warning at all. It printed its success
  banner and exited 0 — the logged-in-looking browser window was the only signal
  the operator had.

## What Didn't Work

- **Trusting the browser as the success signal.** A logged-in-looking page proves
  the *browser* holds a session in memory. It says nothing about whether a token
  was persisted into `~/.comicskingdom_chrome_profile/Default/Cookies`, which is
  the only thing the next morning's run reads.
- **The prior "~9–10 day session lifetime" estimate.** That figure was inferred
  backwards from the dates runs failed, and it was wrong. Reading the cookie
  settles the duration: `__Secure-next-auth.session-token` for host
  `comicskingdom.com` expires exactly **7 days** after it is issued — to the
  microsecond, not approximately.

  ```bash
  cp ~/.comicskingdom_chrome_profile/Default/Cookies /tmp/ck.db
  sqlite3 /tmp/ck.db \
    "SELECT datetime(creation_utc/1000000-11644473600,'unixepoch') AS created,
            datetime(expires_utc/1000000-11644473600,'unixepoch')  AS expires
     FROM cookies WHERE host_key='comicskingdom.com'
       AND name='__Secure-next-auth.session-token';"
  ```

  Failure-date archaeology overestimated the lifetime because it could not see
  when the clock actually started.

  **The clock is not fixed from login — the session rolls on use.** Measured on
  2026-07-28: the 06:17 reauth issued a token expiring `2026-08-04 11:21:25 UTC`;
  after the 06:30 recovery scrape authenticated against the same profile, the
  stored token read `created 2026-07-28 11:30:00 / expires 2026-08-04 11:30:00`.
  Nothing but a scrape happened in between, so an authenticated request re-issues
  the token and restarts the 7 days. Treat "7 days" as *time since last successful
  authenticated use*, not time since login.
- **Lengthening the reauth cadence.** Explicitly rejected by the operator. The
  weekly Monday reauth is the routine that actually gets done; the answer is to
  verify it worked, not to run it more often.

**Root cause of the specific 2026-07-27 no-op is undetermined.** The 06:17
recovery reauth the next morning overwrote the cookie store before anyone could
inspect the prior state. Three mechanisms are on the table, none confirmed:

1. *Unwritten cookie (unverified).* Chrome flushes cookies to its SQLite store on
   clean shutdown, so closing the window by hand instead of letting
   `driver.quit()` close it can leave a newly minted cookie unwritten. The fix is
   designed around this, but it has not been reproduced.
2. *Server-side invalidation (unverified, and newly plausible).* The operator
   logged **out** before logging back in. A logout invalidates the session at the
   provider, and the rolling-session behaviour above means the stored cookie's
   `expires` value is the provider's word about a session it can revoke
   independently. A cookie can therefore sit on disk unexpired while the server
   already rejects it — which looks identical, locally, to a healthy session.
3. *Race in the login helper (weakest).* `wait_for_manual_login`
   (`scripts/comicskingdom_scraper_individual.py:216`) navigates to `/login` and
   its success condition is only that the URL no longer contains `login`
   (`:272`) — which an already-authenticated session satisfies without any new
   token being minted. But a gate ahead of that loop returns `False` when no
   username field is found (`:248-250`), which is what an immediate redirect would
   produce. So this only fires as a race — form renders, field found, redirect
   lands afterwards — and it does not fit the reported symptom of a success banner
   and a zero exit.

## Solution

PR #179 makes the invisible clock visible and turns "the reauth worked" from a
judgement call into an assertion.

**New: `scripts/check_ck_session.py`** reads the token expiry straight out of the
profile's cookie store. It copies the DB to a temp dir and opens the copy
read-only (`scripts/check_ck_session.py:65-66`), so it is safe to run while Chrome
holds the profile and can never mutate the live session. `evaluate()` classifies
the result as `ok | expiring | expired | missing` (`:86`) and `main()` exits
non-zero for anything but `ok` (`:167`). The warn threshold is 2 days (`:34`) —
enough to leave two whole mornings to act before the 03:06 run needs the token.

```bash
python scripts/check_ck_session.py
# ✅ Comics Kingdom session ok: 6.8 days remaining (2026-08-04 11:30 UTC).
```

**Changed: `scripts/reauth_comicskingdom.py`** now proves the login issued a
token. It records the expiry before opening the browser (`:57`) and reads it again
**after** `driver.quit()` (`:77`) — the ordering is load-bearing, because under the
leading hypothesis a read before the quit could still see pre-login state. It then
calls `describe_renewal()` (`scripts/check_ck_session.py:112`) and returns non-zero
when the expiry did not move (`scripts/reauth_comicskingdom.py:86`):

```
❌ Session expiry did NOT move (still 2026-08-01 09:14 UTC). The login did not
   produce a new token, so it will expire on the old schedule (4.2 days).
   Re-run the reauth.
```

**Changed: the daily pipeline** runs the same check after the scrape invariants
and records a `cksession:expiry` failure key when it exits non-zero
(`scripts/local_master_update.sh:330-334`), opening a `[pipeline] Comics Kingdom
session needs a reauth` issue. Because `cksession` is in `ALERT_COVERED`, the
alert clears itself once a good reauth lands.

Operator runbook lives in
[docs/LOCAL_AUTOMATION_README.md](../../LOCAL_AUTOMATION_README.md) — not repeated
here. Coverage is in `tests/test_check_ck_session.py`, including a test that
reading the expiry does not mutate the profile, and `TestDescribeRenewal` cases for
an unchanged expiry, an expiry moving backwards, a missing token after login, and
a first-ever login.

## Why This Works

The cookie is the authoritative record of the session, and it was the one thing
nobody read. Every other signal in the loop is a proxy: a logged-in-looking page,
a redirect away from `/login`, a script exiting 0. All three were green on
2026-07-27 while the state that mattered — the expiry on
`__Secure-next-auth.session-token` — had not moved.

The margin makes this unforgiving. The token lasts 7 days from its last
authenticated use, and the reauth cadence is 7 days, so a reauth that mints
nothing leaves hours of slack rather than days: a Monday reauth covers the
following Monday's 03:06 run and dies before Tuesday's. Under that geometry a
single silent no-op is not a degraded state that self-corrects at the next
reauth — it is an outage the next morning.

**Know what this check cannot tell you.** It reads the provider's stored claim
about the session; it does not ask the provider whether that session is still
valid. Because the session can be revoked server-side — a logout being the obvious
way — an unexpired cookie is necessary but not sufficient. The authority on
validity remains the pipeline's own auth probe (`is_authenticated`), which makes a
real request. Read the expiry check as an early warning that buys days of notice,
not as proof the next run will authenticate.

The fix does not try to decide which of the two hypothesized mechanisms swallowed
the token. It makes either one loud at the moment it happens, while the operator
is still at the keyboard. Reading before `driver.quit()` would defeat the check
entirely under the leading hypothesis, since the value on disk would still be the
pre-login one — hence the ordering comment at the call site, so a future refactor
does not "tidy" the read upward.

## Prevention

- **Verify persisted state, not UI state, for any browser-seeded credential.** The
  same shape applies to TinyView's profile-based session: "the browser looks logged
  in" is not evidence that tomorrow's run will authenticate. Assert against the
  artifact the unattended run actually consumes.
- **Measure token lifetimes; don't infer them from failure dates.** The 9–10 day
  estimate came from failure-date archaeology and was off by ~30%. One `sqlite3`
  query against a copy of the cookie store settles it — and read `creation_utc`
  alongside `expires_utc`, or a rolling session will look like a fixed one.
- **When cadence equals lifetime, add verification rather than frequency.** A
  shorter interval with no verification has the same failure mode, just less often.
- **Never query a live Chrome profile in place.** Copy the cookie DB and open the
  copy read-only. Reading the original risks lock contention at best and corrupting
  the operator's only working session at worst.
- **A reauth helper must exit non-zero when it did not reauth.** Exit status is what
  a wrapper or future cron job reads; a helper that prints a success banner and
  returns 0 on a no-op cannot be automated against.
- **If it recurs, capture the cookie DB before re-running the reauth.** That is the
  evidence needed to promote or discard the clean-shutdown hypothesis — and it is
  exactly what was lost on 2026-07-28.

## Related

- [comicskingdom-hang-diagnosis.md](comicskingdom-hang-diagnosis.md) — introduced the
  persistent Chrome profile this failure mode lives in. Note the forward correction:
  that doc's era of CK failures were hangs misread as expiry; these are genuinely
  expiry, and `check_ck_session.py` now distinguishes them in one command.
- [pipeline-silent-failure-on-wrong-branch.md](pipeline-silent-failure-on-wrong-branch.md)
  — same-day sibling with the same shape at a different layer: an operation
  reporting success while its intended effect never happened. Its *Lesson* section is
  the sharpest statement of the shared principle.
- [github-self-authored-issues-dont-notify.md](../best-practices/github-self-authored-issues-dont-notify.md)
  — the prerequisite that makes the daily `cksession` alert actually reach a human.
