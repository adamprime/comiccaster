---
title: A scrape that produced nothing passed as success — existence checks aren't data checks
date: 2026-08-05
category: logic-errors
module: pipeline
problem_type: silent-failure
component: local_master_update.sh / invariant guard
severity: medium
applies_when:
  - "A run reports ALL SUCCESS but a feed quietly stops getting new entries"
  - "A subscriber reports 'comic X stopped updating' with nothing in the logs"
  - "data/<src>_$DATE.json exists but is `[]` or has far fewer entries than usual"
  - "Adding a new source and wondering what the pipeline actually verifies"
tags: [invariant, silent-failure, scraping, alerting, tinyview, comicskingdom, thresholds]
stack: [bash, python]
github_issues: [148, 151]
---

## TL;DR

The invariant guard asked one question: does `data/<src>_$DATE.json` exist? A
scrape that ran, authenticated, wrote a well-formed file and put **nothing** in
it satisfied that perfectly.

Real instance, found while investigating something else: on **2026-08-03**
TinyView scraped zero comics and wrote `[]`. The pipeline said:

```
✅ TinyView: tinyview_2026-08-03.json present
ComicCaster Master Update Complete (ALL SUCCESS) - Mon Aug  3 03:20:42 CDT 2026
```

No issue, no alert, nobody told. It had happened ~10 times over nine months.

## Why nothing downstream catches it

This is the part that makes it genuinely invisible rather than merely unnoticed.

The feed generator builds each feed from a **90-day window**. A day that
contributed nothing therefore produces a feed that is structurally perfect,
recently updated, and one entry short. There is no empty feed to spot, no error
to grep, no visual tell. The only observable is a strip that never showed up —
which is why the de facto alarm has been *a subscriber opening a GitHub issue*.

The scrapers help less than they look like they do. Comics Kingdom's only
quantity gate is:

```python
if not results:          # literally zero
    return 1
```

So 1 comic out of a 153-comic catalog exits 0 and prints
`✅ SUCCESS! Scraped 1 comics`.

## Contrast: the loud failure

The same week, CK's session was invalidated server-side. `is_authenticated`
found itself redirected to login, the scraper returned 1, and issue #183 was
filed six minutes later. That path works and needed no change. **The gap was
never missing alarms — it was success being asserted without evidence.**

## The fix

`scripts/check_scrape_counts.py` asserts a plausible entry count; the invariant
guard calls it after the existence check and records a normal `<slug>:invariant`
failure, so it alerts and self-clears like any other source.

Sources are registered in one `SOURCE_RULES` dict (same "declare it in one
place" shape as `scraper_factory.py`) holding the payload key — some sources are
a top-level list, others wrap it in `cartoons`/`comics` — and a minimum.

### Setting thresholds honestly

Minimums come from observed history and sit **well below** the real floor: they
exist to catch a collapse, not to police daily wobble. Backtested against all
1350 scrape files, restricted to the current era (445 files since 2026-06-10):

| Result | Count |
| --- | --- |
| Would alert | 3 — all genuine TinyView zero-days |
| False positives | 0 |

Older files do trip it, and that is expected rather than a tuning failure:
**both catalogs grew** (CK 119 → 153 around 2026-03; GoComics ~85 → ~250).
Thresholds describe today's system, so re-check them when a catalog changes.

The backtest also retro-flagged CK at 119–129 entries on 2026-06-02..08 — the
window immediately preceding user issues #148 and #151. This check would have
caught that days before anyone reported it.

### Two deliberate judgement calls

- **`farside_new` is exempt** (`minimum: 0`). It has returned 0 every day since
  the site added bot protection, and the recorded decision was to keep the feed
  rather than chase it. A minimum of 1 would open an issue every morning
  forever — which is how alerting gets ignored.
- **An unregistered source passes.** Adding a scraper must not turn its first
  run red. The message says plainly that nothing was verified, so it cannot be
  mistaken for a check that ran.

## The general lesson

An existence check reads as verification but asserts almost nothing. When a
guard's pass condition is cheaper to satisfy than the work it is guarding, it
will eventually pass without the work having happened. Ask what the *thinnest
possible artifact* that satisfies the check looks like — here, a two-byte file
— and decide whether that should count as success.

Related: `check_ck_session.py` had the mirror-image problem — it reported
"session ok" from cookie expiry alone, and CK refreshes that expiry even on
requests it rejects, so it printed a green line during the very run where the
scraper was turned away. Its passing message now describes the cookie and
disclaims the health claim; see that script's docstring.
