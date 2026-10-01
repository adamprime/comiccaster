---
title: "Far Side Daily Dose recorded yesterday's comics under today's date when the site published late"
date: 2026-10-01
category: logic-errors
module: farside
problem_type: logic_error
component: comiccaster/farside_scraper.py / scripts/scrape_farside.py
severity: medium
symptoms:
  - "The 2026-10-01 Daily Dose items showed Sep 30's five comics; thefarside.com/2026/10/01 showed five different ones"
  - "data/farside_daily_2026-10-01.json held the same data-ids (22797-22801) and images as farside_daily_2026-09-30.json"
  - "The run reported success: the scrape found 5 comics, which passes the invariant guard's count check"
root_cause: logic_error
resolution_type: code_fix
applies_when:
  - "A Far Side Daily Dose day in the feed repeats the previous day's comics"
  - "Changing how the Far Side scraper fetches dated pages"
tags: [farside, redirect, upstream-timing, silent-wrong-data, feed-guid]
---

# Far Side Daily Dose recorded yesterday's comics under today's date when the site published late

## TL;DR

`thefarside.com/YYYY/MM/DD` for a date the site hasn't published yet does not
404. It 302-redirects to the homepage, which shows the newest dose that *is*
out. `requests` follows the redirect silently, so the scraper parsed the
homepage and filed yesterday's five comics under today's date. The scraper now
treats a dated fetch that lands off its date as "not published yet" and writes
no file for that date. The next run's 3-day window records it once it exists.

## Problem

Pass 1 scrapes at about 04:20 Eastern. On nearly every day the site has already
published that date's dose by then. On the two days it hadn't (2026-05-28 and
2026-10-01 out of 169 days scraped from 2026-04-16), the dated request
redirected to the homepage and the scraper recorded the previous day's dose as
today's.

The data healed itself the next morning, because each run re-scrapes the
3-day window and overwrites those files. Subscribers didn't get the fix. Feed
item guids are the dated permalink (`https://www.thefarside.com/2026/10/01/0`),
not the comic, so a reader that already fetched the wrong items treats the
corrected ones as already seen. That day's real dose never reached them.

## How it was found

The first-committed version of every `farside_daily_*.json` was compared with
the previous day's. Only 05-28 and 10-01 matched. Fetching live confirmed the
mechanism: `/2026/10/02` (not yet published) returned a 302 to `/`, and the
homepage's comics matched the latest published date.

## Solution

`FarsideScraper.fetch_comic_page` checks the final URL of a Daily Dose fetch.
If `/{date}` is no longer in its path, it logs a warning and returns `None`
without retrying, since a retry seconds later won't publish the date.
`scrape_daily_dose` then returns `None`, and `scripts/scrape_farside.py` skips
that date (it already did this for an empty scrape). Tests:
`tests/test_farside_scraper.py`.

Skipping the date is better than writing it later. The unpublished date first
shows up in the next run, under guids no reader has seen, so subscribers get
the real comics a day late instead of never.

## Known side effect

The invariant guard in `scripts/local_master_update.sh` expects
`data/farside_daily_$DATE_STR.json`. On a late-publish morning that file won't
exist, so the run opens a Far Side invariant issue ("... is missing"). The next
run writes the file and closes the issue. At about 2 occurrences in 169 days,
we decided the occasional self-closing issue was cheaper than weakening the
guard. If it becomes noisy, the fix belongs in the guard, not in writing a
placeholder file.

## Prevention

- When a scraper requests a URL that names its target (a date, a slug), check
  where the response actually came from, not only its status. A redirect to a
  "latest" page returns 200 with plausible content and passes every count check.
- A wrong-data scrape that heals later still reaches subscribers wrong if feed
  guids are positional. Prefer not writing over writing a guess.
