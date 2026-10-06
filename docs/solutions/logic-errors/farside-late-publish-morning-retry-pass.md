---
title: "Far Side Daily Dose published after the 03:05 run; a morning retry pass ships it the same morning"
date: 2026-10-06
category: logic-errors
module: farside
problem_type: integration_issue
component: scripts/local_farside_morning.sh / scripts/farside_morning.py
severity: medium
symptoms:
  - "thefarside.com had not published the Daily Dose by the 03:20 CDT Pass 1 scrape on 2026-10-01, 10-02 and 10-03; before that only 2026-05-28 was late in 168 days"
  - "On 10-02 and 10-03 the invariant guard reported data/farside_daily_<today>.json missing (issue #219)"
  - "Subscribers got each late day's strips about 24 hours late, unless someone filled the gap by hand"
root_cause: async_timing
resolution_type: workflow_improvement
applies_when:
  - "A source publishes at an unknown or drifting time after the nightly run"
  - "Adding another scheduled pass that commits and pushes to main alongside Pass 1 and Pass 2"
  - "Reading a Far Side alert, the slot log, or Pass 1's morning-pass check"
  - "Choosing whether to move the Far Side slots or narrow their window"
tags: [farside, upstream-timing, retry, launchagent, pipeline-lock, alerting, slot-log, late-publish]
related_components: [scripts/local_master_update.sh, scripts/check_pipeline_heartbeat.py, scripts/report_pipeline_failures.py, .github/workflows/pipeline-alert.yml]
related_issues: [219, 220]
---

# Far Side Daily Dose published after the 03:05 run; a morning retry pass ships it the same morning

## Problem

From 2026-10-01, thefarside.com began publishing its Daily Dose after Pass 1's 03:20 CDT scrape. Since the redirect fix (see the related doc), the scraper correctly writes no file for an unpublished date. That turned every late morning into a missing-file alert, and the dose waited a full day for the next Pass 1. Fixed by a separate Far Side morning pass (PR #220) that retries every 30 minutes and ships the dose the first time it finds it.

## Symptoms

- 2026-10-01, 10-02 and 10-03 were all late. Before that, only 2026-05-28 was late in the 168 days scraped from 2026-04-16.
- On 10-01 the old scraper filed Sep 30's strips under 10-01, so nothing flagged it. That morning's redirect fix (see the related doc) turned the next two late mornings into missing files.
- On 10-02 and 10-03 the guard reported `data/farside_daily_<today>.json` missing. Issue #219 opened on 10-02 and gained a "still failing" comment on 10-03. The operator filled 10-01 and 10-02 by hand, and 10-03 with the first morning-pass run.
- The publish time could only be bounded: after 03:20 CDT on each late day, and up by the hand-fill commits (Thu 10-01 08:43, Fri 10-02 09:20).

## What Didn't Work

- **Moving Pass 1 later.** That moves all seven sources to fix one, and pushes GoComics and Comics Kingdom further into the operator's day. The operator kept Pass 1 at 03:05 and moved only Far Side.
- **One fixed later run, or adding Far Side to the 13:00 Pass 2.** The publish time was unknown and had drifted, so any fixed time was a guess. It would ship late on early days, and might still miss on a late one. A 13:00 slot would have shipped every dose at least seven hours after it appeared.
- **Treating "a local file exists" as "already shipped".** A file can exist locally after a failed push. Each slot instead checks the copy on `origin/main` against the count rule (KTD2 in the plan).
- **A daily-only scraper mode that took only one date.** An early plan draft had `--daily-only` scrape a single date. Pass 1 still needs the usual three-day window for that, so daily-only with no `--date` scrapes the window and with `--date` scrapes only that date (`scripts/scrape_farside.py`).
- **Defects that code review caught before merge** (fixed in PR #220 before it merged):
  - Failure paths used `git reset --hard` *after* the safe-sync check. An operator edit made between the check and the failure could be discarded. Failure paths now unstage and restore only the slot's own paths, or use `git reset --keep` (`local_farside_morning.sh:210-216`, `:256`).
  - `git status` piped straight into the helper meant a failing status arrived as empty input, which reads as a clean checkout. The output is now captured and its exit code checked first (`:172-179`).
  - The already-shipped probe used `--final` before noon, so a short dose that Pass 1 or a catch-up run had committed overnight counted as shipped and ended the morning's retries. The probe now uses the slot's own finality, so before noon a short dose is re-scraped (`:129-145`).
  - A simplification moved a temp-file removal after an early `exit 0`, so the file leaked on the already-shipped path.

## Solution

A LaunchAgent, `com.comiccaster.farside`, runs `scripts/mini_farside_morning.sh` (host environment), which execs `scripts/local_farside_morning.sh`, every 30 minutes from 03:30 to 12:00. The install steps and plist are in `docs/LOCAL_AUTOMATION_README.md`.

**Each slot:**

1. Works out today's date and whether this is the final slot (hour ≥ 12, `scripts/farside_morning.py:77-78`).
2. Takes the shared pipeline lock. A non-final slot does not wait: if the lock is busy it logs `lock-busy` and exits. The noon slot waits up to 30 minutes so a long catch-up run cannot swallow the alert.
3. Fetches refs and checks `origin/main`'s copy of today's file. If that is already a complete dose, it logs `already-shipped` and exits.
4. Scrapes today's Daily Dose only (`scrape_farside.py --daily-only --date <today>`) and judges it. A dose ships at exactly 5 strips Monday to Friday and 2 on Saturday and Sunday (`farside_morning.py:81-104`). The noon slot ships anything that passes the guard's minimum.
5. To ship, it runs the SSH preflight, then the safe-sync check. The checkout must be on `main`, its HEAD an ancestor of `origin/main`, with no tracked changes except the slot's own daily file. Then it resets to `origin/main`, carrying its own file across, and regenerates.
6. Commits exactly two paths, `data/farside_daily_<date>.json` and `public/feeds/farside-daily.xml`, as `Far Side Daily Dose for <date>`. The body names the last slot that missed. It restores `farside-new.xml`, which the generator also rewrites, then pushes and verifies the push landed.

**Alerting and Pass 1:**

- Only a shipping slot and an unshipped noon slot dispatch `pipeline-alert.yml` (`run=farside-morning`, `covered=farside`). A shipping slot closes any open Far Side issue; earlier misses stay in the log.
- `farside` now means the Daily Dose in every pass, and New Stuff reports under its own `farside-new` slug. Otherwise a morning success, which never examines New Stuff, could close a New Stuff issue.
- Pass 1 still scrapes Far Side's three-day window and New Stuff. Its guard now checks **yesterday's** daily file (`local_master_update.sh:361`), plus whether yesterday's morning pass reached a terminal outcome. A missing outcome is reported as `farside:morning-pass` (`:372-373`).
- The commit subject deliberately matches none of the heartbeat's prefixes (`check_pipeline_heartbeat.py:43-50`), so a morning commit cannot hide a dead Pass 1.

**Shared lock:** Pass 1, Pass 2 and the morning pass each re-run themselves under macOS `/usr/bin/lockf` on `logs/pipeline.lock` when `PIPELINE_LOCK_HELD` is unset. The kernel releases the lock when the process exits, so there is no stale-lock cleanup, and a lingering Chrome child never holds it. lockf exits 75 on timeout; Pass 1 and Pass 2 log "did not run" when that happens.

**Slot log:** `logs/farside_morning_slots.log` has one tab-separated line per slot: ISO timestamp with UTC offset, dose date, outcome, strip count. Terminal outcomes are `shipped`, `already-shipped` and `final-unshipped`; misses are `unpublished` and `incomplete` (`farside_morning.py:59-61`). The offset keeps lines comparable across DST.

## Why This Works

The publish time is the unknown, so the fix measures it instead of guessing. Retrying every 30 minutes bounds the delay to one slot whenever the site publishes, and the log records the window for free. Splitting the Far Side guard (yesterday in Pass 1, today in the morning pass) means no pass checks a file it could not yet have. Pass 1's check that yesterday's morning pass finished means a morning pass that silently never ran still alerts within a day.

## Prevention

### Measured publish window (watch, 2026-10-04 to 10-06)

| Morning | Last miss | Shipped | Strips | Commit |
|---|---|---|---|---|
| Sun 10-04 | 06:00 | 06:30 | 2 | 1b21687ea1 |
| Mon 10-05 | 05:30 | 06:00 | 5 | ed7480e676 |
| Tue 10-06 | 05:30 | 06:00 | 5 | 1730d7c223 |

Each day produced one two-file commit, and every later slot logged `already-shipped`. There were no Far Side issues and nothing in the launchd stderr log. Pass 1's morning-pass check passed on 10-04, 10-05 and 10-06. The site posted between 05:30 and 06:30 CDT (06:30-07:30 ET). The 03:30-05:00 slots missed on all three watched days. Each costs a refs fetch plus one scrape request. The plan defers picking a single fixed time until a week or more of slot logs exists.

### Reading it

- Read `logs/farside_morning_slots.log` for a day's outcome: `grep <date> logs/farside_morning_slots.log`. The run detail is in `logs/farside_morning.log`.
- A Far Side issue now means the noon slot could not ship. The kind names the last cause (unpublished, incomplete, checkout, push, …). `farside:morning-pass` from Pass 1 means yesterday's pass logged no terminal outcome at all.
- To fill a missed day by hand while the dose is still on the site, run the morning pass once (`bash scripts/mini_farside_morning.sh`). After noon that run is a final slot. This is a deliberate production action.

### Adding another scheduled pass

Reuse the same pieces:

- the lockf re-exec preamble;
- a commit subject outside the heartbeat prefixes;
- an alert slug that means one thing in every pass;
- a safe-sync check before any reset;
- `--keep` or path-scoped undo on failure paths.

### Known gaps

PR #220 lists the review findings it did not apply. Notable ones:

- fetches and `ssh -T` have no timeout while holding the lock;
- a noon slot whose lock wait times out dispatches nothing;
- `generate_farside_feeds.py` exits 1 when only the New Stuff half fails, which would block every slot from shipping;
- `check-terminal` skips silently if the slot log is deleted.

### Tests

`tests/test_farside_morning.py` covers the slot date, finality, the weekday and weekend counts, the ship decision, the safe-sync verdicts, the log format and `check-terminal`'s exit codes, including an unreadable log. `tests/test_scrape_farside.py` covers the scraper's new flags. `tests/test_check_pipeline_heartbeat.py` pins that morning commits are ignored. `tests/test_report_pipeline_failures.py` covers the `farside-new` slug.

## Related Issues

- Issue #219, closed 2026-10-03 13:29 CDT by the first morning-pass run (a manual run right after PR #220 merged); plan `docs/plans/2026-10-03-1005-fix-farside-morning-retry-pass-plan.md`.
- `docs/solutions/logic-errors/farside-unpublished-date-recorded-yesterdays-dose.md`: the redirect fix that made late publishes visible as missing files instead of yesterday's comics under today's date.
- `docs/solutions/logic-errors/gocomics-favorites-page-timing.md`: the same late-publisher problem for GoComics, solved with Pass 2.
- `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`: the invariant guard this splits between passes.
- `docs/solutions/logic-errors/pipeline-silent-failure-on-wrong-branch.md`: why the slot never switches branches and refuses to sync an unsafe checkout.
