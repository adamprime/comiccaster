---
title: Comics Kingdom has two independent session clocks — the cookie expiry is not session health
date: 2026-08-18
category: logic-errors
module: scrapers
problem_type: environment
component: check_ck_session.py / comicskingdom_scraper_individual.py
severity: medium
applies_when:
  - "CK auth fails while check_ck_session reports a healthy '7.0 days remaining'"
  - "Deciding whether the weekly Monday reauth is actually necessary"
  - "A CK failure lands on a Tuesday or Wednesday"
  - "check_ck_session reports 'No Comics Kingdom session token found'"
tags: [comicskingdom, session, cookies, ttl, reauth, alerting, misdiagnosis]
stack: [selenium, chrome]
github_issues: [178, 183, 187, 188]
---

## TL;DR

Comics Kingdom sessions are governed by **two unrelated clocks**, and conflating
them produces confident, wrong diagnoses:

| Clock | Behavior | Who can read it |
| --- | --- | --- |
| **Client cookie expiry** | rolls forward on *every* request — including ones CK redirects to login | `check_ck_session.py` |
| **Server session TTL** | fixed **~7 days from login**; pipeline traffic does not extend it | only a real scrape |

The cookie can report "7.0 days remaining" over a session the server killed days
ago. **Only a reauth resets the server clock.**

## The decisive evidence

Every session-type CK failure in the pipeline log lands on a **Tuesday or
Wednesday — 7 of 7**:

```
Apr 28 Tue · Apr 29 Wed · Jun 3 Wed · Jul 7 Tue · Jul 28 Tue · Aug 5 Wed · Aug 18 Tue
```

Never Thu/Fri/Sat/Sun/Mon. The two failures that *do* fall elsewhere had other
causes entirely — Jun 9 (ChromeDriver/Chrome major mismatch) and **Fri Aug 7**
(Chrome auto-update, see the sibling doc).

That clustering is the operator's **Monday reauth** showing through: reauth
Monday → server TTL covers to the following Monday → a missed or failed Monday
reauth surfaces as a Tuesday 03:07 failure. The long gaps between failures (35d,
34d, 21d) are just weeks where the reauth landed on time.

Confirmed 2026-08-18: the operator missed Monday Aug 17, and Tuesday Aug 18
failed — while the cookie had been rolling forward perfectly all week:

| Run | Cookie says expires | Reality |
| --- | --- | --- |
| Aug 14 | Aug 21 | fine |
| Aug 15 | Aug 22 | fine |
| Aug 16 | Aug 23 | fine |
| Aug 17 03:16 | **Aug 24** | last good scrape |
| Aug 18 03:07 | — | **session dead**, token gone |

A token "valid until Aug 24" cannot expire on Aug 18. The client clock was
healthy and irrelevant.

## Why the token was *missing*, not just stale

At 03:14 the check reported `No Comics Kingdom session token found`. That is
almost certainly a **consequence** of the failure, not its cause: when CK
redirects to login it clears the stale session cookie, so the two failed auth
attempts at 03:07 wiped it, and the check ran seven minutes later. (Inference —
the subsequent reauth overwrote the cookie DB and destroyed the evidence. Which
is itself the standing rule: *read the expiry before reauthing*, since a reauth
destroys the state you would need to diagnose.)

Either way the missing-token branch is the one genuinely reliable signal this
check has — it is unambiguous, and it correctly opened issue #188.

## The corrections this supersedes

Two earlier conclusions in this repo were wrong and are retained here because
each was reached from real evidence:

1. **"The rolling expiry means a daily-succeeding pipeline keeps CK alive
   indefinitely; the risk is a pipeline outage, not the calendar."** False. The
   measurement (the expiry rolls on use) was right; the inference (therefore the
   session survives) does not follow, because it is the wrong clock. Acting on
   this would drop the Monday reauth and cause weekly outages.
2. **"The Aug 5 reauth was probably unnecessary."** False. Aug 5 fits the server
   TTL (Jul 28 06:17 reauth + 7d ≈ Aug 4) and its symptom was a login redirect.
   That reauth was the fix.

## How to diagnose a CK failure

1. **Read the symptom line**, which is the whole tell:
   - `↳ redirected to the login page` → session problem → **reauth**.
   - `↳ navigation failed: <exception>` → transient/browser → **retry**; check
     whether Chrome auto-updated.
2. **Check the weekday.** Tue/Wed after a missed Monday is the common case.
3. **Do not read the expiry as health.** A green line means a cookie exists.

## The general lesson

A measurement can be correct and the inference drawn from it still wrong. "The
expiry rolls forward on every request" was verified from the cookie DB and never
in doubt; the error was treating it as a proxy for something it does not
observe. When a metric is used as a proxy for health, state plainly which
mechanism actually produces the failure — and check whether the proxy can see
that mechanism at all.
