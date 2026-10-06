---
title: "Comics Kingdom vintage reruns: replaying fixed archives on a calendar schedule"
date: 2026-10-06
category: best-practices
module: comicskingdom
problem_type: design_pattern
component: comiccaster/comicskingdom_reruns.py / scripts/comicskingdom_scraper_individual.py / scripts/generate_comicskingdom_feeds.py
severity: medium
applies_when:
  - "A vintage Comics Kingdom feed stopped delivering, or delivered the wrong strip"
  - "Adding a vintage series (The Little King) or changing a series' rerun range"
  - "Moving PR 2's go-live date, which moves every anchor"
  - "Reading the scraper's 'Reruns delivered' and 'Rerun gaps' totals"
  - "Tempted to replace the schedule with a saved cursor or a this-day-N-years-ago rule"
tags: [comics-kingdom, vintage, reruns, schedule, strip-identity, guid, catalog]
related_components: [public/comics_list.json, CONCEPTS.md, tests/test_comicskingdom_reruns.py, tests/test_catalog_source_integrity.py]
related_issues: [216]
---

# Comics Kingdom vintage reruns: replaying fixed archives on a calendar schedule

## Context

32 of Comics Kingdom's 33 vintage series are fixed archives. Their newest post has not changed since February 2026; Beetle Bailey Vintage's is 1967-12-31. Every archived date can still be loaded at `/vintage/<slug>/<YYYY-MM-DD>`. Our feeds therefore sat on one strip for months (issue #216). Bringing Up Father is the exception: Comics Kingdom reposts it daily under 2026 dates, so it is not rerun.

The operator chose daily reruns over leaving the feeds frozen or removing them. Each series replays its archive one day at a time, on a schedule ComicCaster computes. Strip-number stepping was deferred (see below).

## Guidance

### The schedule is a pure calendar function

`comiccaster/comicskingdom_reruns.py`:

```
archive date = start + ((delivery − anchor) mod L)
L = (end − start + 1 day), rounded up to whole weeks
```

- `start` and `end` bound a densely covered stretch of the archive. `anchor` is the delivery date that gets `start`, on the same weekday.
- Rounding `L` up to weeks keeps every archive date on its own weekday, loop after loop, so Sunday pages arrive on Sundays.
- The padding days at the end of a loop point past `end`. The page then shows the last strip, which is not that date's own, so nothing is delivered.
- Before its anchor a series stays on the ordinary path, recording the frozen post as before.

It reads no clock and keeps no cursor. Any host, and any push-recovery regeneration, gets the same answer. A cursor file would be reverted by push recovery's `git reset --hard`, which is what the Far Side New Stuff cursor plan found (`docs/plans/2026-08-02-001-fix-farside-new-stuff-cursor-plan.md`).

The values live on the 32 catalog entries in `public/comics_list.json` as `rerun_start`, `rerun_end` and `rerun_anchor`. `tests/test_catalog_source_integrity.py` checks the following:

- exactly the fixed archives carry them, and Bringing Up Father does not;
- `start ≤ end`;
- each anchor falls on its start's weekday;
- the four daily/Sunday pairs share an offset and a loop length.

### The scraper loads the scheduled date, one page per comic

On and after the anchor, `scrape_all_comics` loads `/vintage/<source slug>/<archive date>` instead of tonight's page. The record keeps `date` as tonight, `url` as the page loaded, and the displayed post's `post_date`, plus `rerun_date`.

- **Delivered:** `post_date == rerun_date`, and the record has images.
- **Gap:** the archive has no strip of its own that date, so the page shows an earlier one. The record keeps both dates and **no images**. It still counts toward the guard's 146-of-156 floor, so a Sunday-only series on a weekday never trips the guard.

The run prints `Reruns delivered: N` and `Rerun gaps: N`, each with slugs and dates. Reruns are not counted as repeats.

### The generator identifies a rerun by its delivery date

Records carrying `rerun_date` are routed before any other rule (`load_window_strips`, `rerun_entries`).

- Guid: `ck-rerun-<slug>-<delivery date>`, following Mr. Boffo's `mrboffo-<date>`.
- Link: the archive page.
- Title and description: the print date.
- pubDate: the delivery date.
- Window: the delivery (file) date.

Gaps are never listed. Once a series has a delivered rerun in the window, its feed lists reruns only. That matters at go-live: the ~89 in-window nights recorded the frozen strip under its post date, and listing those would flood the feed.

## Why This Matters

- **Identity by delivery date** means a later loop that delivers the same archive date is a new item. Identity by print date would deliver each strip once and then go silent after the first loop.
- **"This day N years ago"** stalls once it passes the archive's end, and lands on the wrong weekday. **Stopping at the end** freezes the feed again.
- **The catalog flag `source_variant` stays a display label.** Selecting reruns by catalog field in the generator would turn every in-window post-dated record of a vintage series into a rerun on go-live night. The generator reads only record fields.

## When to Apply

### Changing a range

- **Editing `end`** takes effect only at the next loop, years away; the earliest is 2029.
- **Editing `start` or `anchor`** shifts every later delivery. Already-delivered items keep their guids, because a guid is its delivery date. Later days just map to different strips.
- **Pairs** (The Phantom, Flash Gordon, Mandrake, Tiger) must change together. The integrity test enforces this.

### Moving go-live

Anchors are the first date on or after go-live with the start's weekday. For a pair, the Sunday half takes the daily anchor plus six. If the merge moves, recompute every anchor before merging; ranges stay as measured. A series whose anchor is still in the future simply keeps its old path until then.

### Adding a series (The Little King)

1. Measure its archive range as below.
2. Add the three values.
3. Add its pair to `RERUN_PAIRS` if it has a Sunday half.
4. Bump the integrity test's count of 32.

`docs/solutions/best-practices/catalog-sweep-and-comic-onboarding-by-source.md` points here.

## Examples

### How the ranges were measured (2026-10-06)

All requests came from the scraper's logged-in Chrome profile, outside pipeline hours, paced at about 1.5 s with a stop on the first non-200 response. No session values left the browser. There were about 400 requests in all, with no errors and no 429s.

1. **The range ends.** One `/vintage/<slug>/<date>` page load per series gives the feature record's `ck_oldest_comic` and `ck_latest_comic`.
2. **The taxonomy id.** The WordPress REST API, fetched from inside the logged-in page, took the term id from the latest post (`ck_comic?slug=<latest post slug>&_fields=ck_feature_taxonomy`).
3. **Counts and first posts.** `ck_comic?ck_feature_taxonomy=<id>&_fields=date&orderby=date&order=asc` returns the total in `X-WP-Total` and the first posts.
   - Looking up the taxonomy by slug returns nothing.
   - `ck_feature` is the feature *post*, not the taxonomy.
4. **Dense series** (coverage at or near 100% of the strip's cadence) take their first real post to their last post. Some first posts are not real and were skipped:
   - placeholders dated 1900–1910 (Johnny Hazard, Secret Agent X-9, Tiger and Tiger Sundays);
   - a stray: Beetle Bailey's single 1950-09-04 post, before its real start on 1953-10-05.
5. **Gappy series** were listed date by date at 100 per page. Each took its longest stretch with no hole over 14 days (21 for Sundays).
6. **Pairs** share one week grid. The dailies run Monday to Saturday, and the Sunday half runs one day later at each end. Both halves therefore share an offset and a loop length, and a story's Sunday page lands in its dailies' week.

Comics Kingdom's own `ck_first_date`/`ck_last_date` were wrong for many series. Don't use them as ranges:

- Apartment 3-G says 1970–1978, but its posts run to 2015.
- Krazy Kat says 1922–1938, but its dense run is 1936–1944.
- Thimble Theater says it ends in 1939, but its posts end in 1937.
- Quincy says 1973–1984, against posts from 1971 to 1986.
- The Phantom says 1945–1958, against posts from 1943 to 1959.

### Per-series values (anchors assume go-live 2026-10-07)

| Series | Kind | CK posts (oldest – latest) | Posts | CK's own range fields | Rerun range | L (days) | Anchor |
|---|---|---|---|---|---|---|---|
| `apartment-3-g_1` | gappy | 1970-01-01 – 2015-11-22 | 9075 | 1970-01-01 – 1978-12-30 | 1996-01-07 – 2015-11-22 | 7266 | 2026-10-11 |
| `barney-google-and-snuffy-smith-vintage` | dense | 1936-01-01 – 1949-12-31 | 4839 | 1938-01-01 – 1949-12-31 | 1936-01-01 – 1949-12-31 | 5117 | 2026-10-07 |
| `beetle-bailey-vintage` | dense | 1950-09-04 – 1967-12-31 | 5028 | 1956-01-02 – 1967-12-30 | 1953-10-05 – 1967-12-31 | 5201 | 2026-10-12 |
| `big-ben-bolt` | dense | 1950-02-20 – 1963-12-31 | 4938 | 1950-02-20 – 1963-12-31 | 1950-02-20 – 1963-12-31 | 5068 | 2026-10-12 |
| `boners-ark` | dense | 1968-03-11 – 1978-12-31 | 3932 | 1968-03-04 – 1978-12-30 | 1968-03-11 – 1978-12-31 | 3948 | 2026-10-12 |
| `brick-bradford` | dense | 1937-01-04 – 1952-12-31 | 5324 | 1938-01-01 – 1952-12-31 | 1937-01-04 – 1952-12-31 | 5845 | 2026-10-12 |
| `buz-sawyer` | dense | 1947-01-01 – 1960-12-31 | 4953 | 1949-01-01 – 1960-12-31 | 1947-01-01 – 1960-12-31 | 5117 | 2026-10-07 |
| `flash-gordon-vintage` | dense, pair | 1955-01-01 – 1969-12-31 | 4690 | 1958-01-01 – 1969-12-31 | 1955-01-03 – 1969-12-27 | 5474 | 2026-10-12 |
| `flash-gordon-vintage-sunday` | dense, pair | 1955-01-02 – 1969-12-28 | 783 | 1955-09-04 – 1969-12-28 | 1955-01-09 – 1969-12-28 | 5474 | 2026-10-18 |
| `heart-of-juliet-jones` | dense | 1953-03-09 – 1967-12-31 | 5339 | 1955-01-01 – 1966-12-31 | 1953-03-09 – 1967-12-31 | 5411 | 2026-10-12 |
| `hi-and-lois-vintage` | dense | 1954-10-18 – 1966-12-31 | 4351 | 1954-10-18 – 1966-12-31 | 1954-10-18 – 1966-12-31 | 4459 | 2026-10-12 |
| `johnny-hazard` | dense | 1910-01-01 – 1954-12-31 | 3830 | 1944-06-05 – 1954-12-31 | 1944-06-05 – 1954-12-31 | 3864 | 2026-10-12 |
| `judge-parker-vintage` | gappy | 1968-10-21 – 1981-12-26 | 3777 | 1968-10-21 – 1981-12-26 | 1972-10-02 – 1980-05-19 | 2793 | 2026-10-12 |
| `jungle-jim-sundays` | dense | 1933-12-24 – 1941-12-28 | 404 | 1933-12-24 – 1941-12-28 | 1933-12-24 – 1941-12-28 | 2933 | 2026-10-11 |
| `katzenjammer-kids-vintage-sunday` | dense | 1938-01-02 – 1951-12-30 | 733 | 1938-01-02 – 1951-12-30 | 1938-01-02 – 1951-12-30 | 5117 | 2026-10-11 |
| `king-of-the-royal-mounted` | gappy | 1937-01-04 – 1951-12-31 | 3771 | 1937-01-04 – 1951-12-31 | 1937-01-04 – 1945-02-12 | 2968 | 2026-10-12 |
| `krazy-kat` | gappy | 1922-01-02 – 1944-06-08 | 2931 | 1922-01-02 – 1938-12-31 | 1936-01-01 – 1944-06-08 | 3087 | 2026-10-07 |
| `little-iodine-sundays` | dense | 1949-04-03 – 1962-12-30 | 689 | 1949-04-03 – 1962-12-30 | 1949-04-03 – 1962-12-30 | 5026 | 2026-10-11 |
| `mandrake-the-magician-vintage` | dense, pair | 1938-03-10 – 1951-12-31 | 4318 | 1938-03-10 – 1951-12-31 | 1938-03-14 – 1951-12-29 | 5040 | 2026-10-12 |
| `mandrake-the-magician-vintage-sunday` | dense, pair | 1938-01-30 – 1951-12-30 | 726 | 1938-01-30 – 1951-12-30 | 1938-03-20 – 1951-12-30 | 5040 | 2026-10-18 |
| `mark-trail-vintage` | gappy | 1971-07-05 – 1974-12-31 | 945 | 1971-07-07 – 1974-12-31 | 1972-01-01 – 1974-12-31 | 1099 | 2026-10-10 |
| `office-hours` | dense | 1962-01-01 – 1974-08-03 | 3915 | 1962-01-01 – 1974-08-03 | 1962-01-01 – 1974-08-03 | 4599 | 2026-10-12 |
| `prince-valiant-vintage-sunday` | gappy | 1937-02-13 – 1984-12-30 | 320 | 1980-01-06 – 1984-12-30 | 1980-01-06 – 1984-12-30 | 1827 | 2026-10-11 |
| `quincy` | dense | 1971-04-05 – 1986-01-04 | 4603 | 1973-07-02 – 1984-12-31 | 1971-04-05 – 1986-01-04 | 5390 | 2026-10-12 |
| `radio-patrol` | dense | 1939-01-02 – 1950-12-16 | 3718 | 1939-01-02 – 1950-12-16 | 1939-01-02 – 1950-12-16 | 4368 | 2026-10-12 |
| `rip-kirby` | dense | 1951-01-01 – 1964-12-31 | 4384 | 1951-01-01 – 1964-12-31 | 1951-01-01 – 1964-12-31 | 5117 | 2026-10-12 |
| `secret-agent-x-9` | dense | 1901-01-01 – 1944-12-30 | 2861 | 1935-11-18 – 1944-12-31 | 1935-11-18 – 1944-12-30 | 3332 | 2026-10-12 |
| `the-phantom-vintage` | dense, pair | 1943-01-01 – 1959-12-31 | 5321 | 1945-07-02 – 1958-12-31 | 1943-01-04 – 1959-12-26 | 6202 | 2026-10-12 |
| `the-phantom-vintage-sunday` | dense, pair | 1943-01-03 – 1959-12-27 | 887 | 1947-07-06 – 1958-12-28 | 1943-01-10 – 1959-12-27 | 6202 | 2026-10-18 |
| `thimble-theater` | gappy | 1900-01-01 – 1937-06-26 | 1016 | 1929-01-01 – 1939-12-30 | 1929-01-01 – 1931-12-31 | 1099 | 2026-10-13 |
| `tiger-vintage` | dense, pair | 1900-01-01 – 1972-01-01 | 2084 | 1965-05-03 – 1971-12-31 | 1965-05-03 – 1971-12-25 | 2429 | 2026-10-12 |
| `tiger-vintage-sunday` | dense, pair | 1900-01-07 – 1971-12-26 | 347 | 1965-05-09 – 1971-12-26 | 1965-05-09 – 1971-12-26 | 2429 | 2026-10-18 |

**Gappy series and their holes.** These were split wherever a hole exceeded 14 days. The longest stretch was kept:

- Prince Valiant Sundays: 59 posts in 1937–38, then nothing until 1980.
- Thimble Theater: 1929–31, then only a few months of 1937.
- Krazy Kat: 1922, then 1936–44.
- Apartment 3-G: 1970–73 and 1974–78, then 1996–2015.
- King of the Royal Mounted: 1937–45, then 1948–51.
- Mark Trail: six strips in July 1971, then 1972–74. The plan's AE6 example used 1971-07-05; the measured start is 1972-01-01.
- Judge Parker: 1968–72, 1972–80 and a thin 1980–81.

**Weekday cadence.** Daily-only series (Mon–Sat) deliver nothing on Sundays: the Sunday archive date has no strip of its own, so it is a gap. The same applies to the eight Sunday-only series on weekdays. Most nights therefore show eight or more gaps, and Sundays show one for each daily-only series, all of them by design. Gaps beyond that pattern mean a hole inside a range.

## Deferred

**Strip-number stepping.** Walking each archive post by post instead of by calendar day would remove gap days. It needs an index of roughly 108,000 post dates, which the plan deferred. The gappy series now run only on their dense stretches, so revisit stepping only if a series reads as too sparse.

## Related

- Issue #216 (part 2). Plan: `docs/plans/2026-10-01-1213-fix-ck-own-post-and-vintage-reruns-plan.md`, units U7–U13.
- `docs/solutions/logic-errors/comicskingdom-scraper-recorded-the-page-not-the-post.md`: part 1, the post-date identity that reruns sit beside.
- `docs/solutions/best-practices/mixed-content-and-single-image-comic-sources.md`: delivery-date identity, the Mr. Boffo precedent.
- `CONCEPTS.md`: "Rerun schedule" and "Strip identity".
