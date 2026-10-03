---
title: "TinyView feeds held only the newest strip, and strips sharing a date were lost"
date: 2026-09-29
last_updated: 2026-10-03
category: logic-errors
module: tinyview
problem_type: logic_error
component: scripts/generate_tinyview_feeds_from_data.py / scripts/tinyview_scraper_local_authenticated.py / comiccaster/tinyview_scraper.py / comiccaster/tinyview_strips.py
severity: high
symptoms:
  - "30 of the 31 established TinyView feeds held exactly one <item> (the 31st has never had a feed); nick-anderson.xml held 7 items on 2025-11-20 and 1 from 2025-11-25 onward, when the local authenticated scraper went into service"
  - "Pass 1 on 2026-09-29 logged 49 'No comic found for <slug> on <date>' warnings, all for strips 30-90 days old in the five series added 2026-09-28"
  - "Kowal Comics' five-part 'Bella', filed under one date folder, was recorded as Part 4 four times with Part 3's 14 panels attached; Parts 1-3 were never recorded and Part 5 would have been skipped for good"
  - "The nightly pipeline reported ALL SUCCESS throughout; nothing checked how many items a feed held"
root_cause: logic_error
resolution_type: code_fix
applies_when:
  - "A TinyView feed holds one item although the comic has a real archive"
  - "A multi-part TinyView story filed under one date is missing parts or shows another part's panels"
  - "Changing a generator's feed window, or a plan claims a generator already reads every data file"
  - "Choosing the key a scraper uses to decide a strip is already recorded"
  - "Shipping any change to how a feed is regenerated, where existing item guids must not change"
tags: [tinyview, feed-window, feed-history, dedup, strip-identity, silent-data-loss, backfill]
related_issues: [211, 212, 113, 213, 214, 207]
---

# TinyView feeds held only the newest strip, and strips sharing a date were lost

## TL;DR

Every TinyView feed was rebuilt each night from only the newest strips, because
two reasonable pieces composed badly: the scraper saves each strip once, and the
generator read only the newest night's data file. The April 90-day history
change (#113) skipped the TinyView generator on a plan row that said it "already
loads all files". On the same path, the scraper keyed strips by date, so strips
filed under one date collapsed into one record carrying each other's panels, and
strips 30-90 days old were never fetched. PR #212 made a strip's address its
identity everywhere and built each feed from a 90-day window of strip dates. A
continuity proof and a watched catch-up confirmed no subscriber got a repeat.

## Problem

Every TinyView feed carried only its newest strip, and the scraper feeding it lost
or mangled strips that share a date folder. The cause was two parts that each look
fine alone. The scraper saves each strip once, and the generator read only the
newest night's file (issue #211, fixed in PR #212).

## Symptoms

Observed 2026-09-29:

- **One-item feeds.** 30 of the 31 established TinyView feeds held exactly one
  `<item>`; the 31st, `matt-bors-tinyview`, has never had a feed file.
  In git history `nick-anderson.xml` had 7 items on 2025-11-20 and 1 item from
  2025-11-25 onward. That is when the local authenticated scraper went into
  service.
- **"No comic found" lines.** Pass 1 logged 49 `No comic found for <slug> on <date>`
  warnings. All were for the five series added 2026-09-28, and all were for strips
  30-90 days old.
- **Slow Pass 1.** The run took about 4 minutes longer than usual: Far Side started
  at 03:23:56 instead of around 03:20.
- **Bella Part 4 recorded four times.** Kowal Comics files all five parts of "Bella"
  under one date folder, `2026/09/24`, although the parts posted 09-26 through 09-29.
  `data/tinyview_2026-09-28.json` held `bella-part-4-of-5` **four times**, and each
  copy had 32 images: its own 18 plus all 14 of Part 3's panels. Parts 1-3 were never
  recorded, and Part 5 would have been skipped for good.
- **Wider damage.** In the 90 days before the fix, 7 saved strips (Bella Part 4
  among them) carried a same-date sibling's images, and 26 strips had been skipped
  because a sibling on the same date was already recorded. The catch-up recovered
  all 26.
- **All green.** The pipeline reported success every night.

## What Didn't Work

**A plan row that said "no change needed".** The April 90-day history plan (#113,
`docs/plans/2026-04-15-001-feat-extend-feed-history-90-days-plan.md`) has a research
row that reads "TinyView generator | All files | None | No change needed" (`:51`).
It also says "TinyView generator already loads all files, so no change needed there"
(`:85`). Neither was ever true. Before #212 the generator's
`find_latest_tinyview_data()` returned `sorted(glob('tinyview_*.json'))[-1]`, and that
code had not changed since 2025-12-06.

The same plan's Key Decisions say generators "merge new entries into existing feed
XML (preserving old entries)" (`:40`). `generate_feed` does no merging. It starts a
new feed (`comiccaster/feed_generator.py:343`) and writes the whole file
(`:382`). GoComics and Comics Kingdom reached 90 items only because their generators
loaded 90 files (the Comics Kingdom generator has read all saved history since
PR #217). So #113 raised only the TinyView scraper's lookback, from 15 to 90
days, and TinyView feeds stayed at one item.

**The guard counted files, not feed length.** TinyView's count floor is 1
(`scripts/check_scrape_counts.py:50`). Each night's file held that night's new
strips, so it passed. No check looked at how many items a feed held.

**Tests that asserted the old behavior.** #212 deliberately updated three
existing scraper tests and left a comment in each explaining why:

- `test_mixed_image_sources_filtering` asserted that the `strip1/`, `strip2/` and
  `strip3/` panels are all kept because they share a date
  (`tests/test_tinyview_scraper.py:522`). Keeping all three is the Bella bug.
- `test_tinyview_url_construction` asserted that the series listing loads first
  (`:102`). That listing load is where the 30-day lookup came from.
- In `test_lazy_loading_image_detection`, the `data-src` fallback accepted any
  tinyview.com image (`:193`).

**Dead ends inside the fix itself:**

- *The plan's premise that "a strip is never dated after the file that saved it."*
  The first window skipped data files named before the window start. Review found
  that the premise is false: an Itchy Feet strip dated 2026-03-01 is saved in
  `data/tinyview_2026-02-28.json`. The skip would have dropped a boundary strip a day
  early. The generator now reads every strictly named file, and only the per-strip
  date check bounds the window.
- *Deriving the CDN folder from the feed slug.* The feed `fowl-language-tinyview` is
  filed at `fowl-language` on TinyView. A slug-based folder would have dropped every
  Fowl Language image. Without the empty-feed guard, it would also have written a
  0-item feed over the live one. The plan's flow analysis caught this before any
  code was written.

## Solution

PR #212, merged 2026-09-29. Suite: 622 passed at merge.

### 1. One definition of a strip: `comiccaster/tinyview_strips.py`

This is a new module with no Selenium dependency, so the network-free generator can
import it (`:17`). The scraper and the generator both use it:

- `canonical_strip_url` (`:30-38`) returns scheme, lower-cased host and path. It
  drops the query, the fragment and any trailing slash. This one string is the
  recorded key, the dedup key and the feed guid.
- `strip_folder` (`:41-51`) returns `<series>/<YYYY>/<MM>/<DD>/<strip>`. It returns
  `None` when the address is not a single strip.
- `image_belongs_to_strip` (`:54-64`) accepts only images under that folder on
  `cdn.tinyview.com`:

```python
folder = strip_folder(strip_url)
if folder is None:
    return False
image = urlparse(image_url)
return image.netloc.lower() == CDN_HOST and image.path.startswith(f'/{folder}/')
```

The folder comes from the **address, never the feed slug** (`:14-15`). The trailing
`/` in the prefix stops a strip from claiming the images of a sibling whose name
begins with its own name.

### 2. Generator: a 90-day window of strip dates, anchored on the data

`scripts/generate_tinyview_feeds_from_data.py`:

- `find_tinyview_data_files` reads every file whose name matches
  `^tinyview_(\d{4}-\d{2}-\d{2})\.json$` (`:47`), oldest first. The strict pattern
  skips `data/tinyview_2025-11-16_backup.json`.
- `own_strip` (`:89-111`) narrows each record to its own images and returns
  `(strip date, canonical address, record)`.
- `load_window_strips` (`:114-145`) builds the window:

```python
newest = files[-1][0]
window_start = newest - timedelta(days=WINDOW_DAYS)
...
for _, path in files:
    for position, record in enumerate(read_data_file(path)):
        ...
        if strip_date < window_start or not record['images'] or address in strips:
            continue
        strips[address] = (strip_date, record)
...
sorted(strips.items(), key=lambda item: (item[1][0], item[0]))
```

  - The window is measured in strip dates, back from the newest data file. The
    boundary day counts as inside.
  - Dedup is by canonical address. The earliest-recorded usable copy wins.
  - Output is ordered by (strip date, address).
- **Item fields are unchanged** (`:181-192`): guid = strip url, title = record
  `name`, pubDate = strip date at 23:59:59 UTC.
- **It never writes an empty feed** (`:194-197`). A comic with no usable strip in the
  window keeps its file byte-identical. There are 13 dormant feeds whose 2025
  placeholder items the data can't reproduce.

### 3. Scraper: fetch by address, keep only the strip's own panels

`comiccaster/tinyview_scraper.py`:

- `fetch_comic_page`, `extract_images` and `scrape_comic` take a **keyword-only**
  `strip_url` (`:282-283`, `:388-389`, `:496-497`). The abstract signatures in
  `BaseScraper` are unchanged (`comiccaster/base_scraper.py:37,63,76`). Older callers
  passed a title slug as the third positional argument, so keyword-only means that
  argument can never become the address.
- Given an address, the page loads directly, with no second listing load. The
  date-lookup fallback runs only when no address is given (`:299-308`), and it now
  uses the listing's 90-day default.
- `_own_panel_url` (`:43-61`) unwraps Next.js `/_next/image?url=...` proxy srcs and
  then applies `image_belongs_to_strip`. It is used in three places:
  - the panel-load wait, `_count_own_panels` (`:277-280`), which replaces the old
    `img[src*="cdn.tinyview.com/{slug}/{date}"]` CSS selector;
  - `src` extraction;
  - the `data-src` fallback (`:413-433`).
- If a page shows none of the strip's own panels, `scrape_comic` returns `None`
  (`:524-527`). The strip is not recorded, and the next night retries it. The record's
  `url` is the canonical address (`:536`).

### 4. Nightly script: recorded means "this address is saved"

`scripts/tinyview_scraper_local_authenticated.py`:

- `load_recorded_strips` (`:57-90`) collects the canonical addresses across all data
  files through `canonical_addresses` (`:38-54`), which skips malformed records. The
  old `load_existing_data` built a per-slug set of *dates*.
- The listing is deduped by address, and each new strip is fetched by its listed
  address (`:126-130`, `:144`):

```python
listed = {}
for comic_data in recent_comics:
    listed.setdefault(canonical_strip_url(comic_data['url']), comic_data)
new_strips = [(address, data) for address, data in listed.items() if address not in recorded]
```

- Each series logs the listed strips it failed to record, and the run logs a
  greppable total, `Listed but not recorded: N` (`:254`). On the production path an
  address is always passed, so `No comic found` can no longer appear there.
- `merge_with_existing` (`:266-296`) adds a same-day rerun's strips to the day's
  existing file, keyed by address, and the existing record wins. The old code
  overwrote the file, which erased the first run's strips. A rerun that found nothing
  wrote `[]` and tripped the TinyView invariant. The GoComics twin of this function
  keys on slug and lets the new record win. TinyView can't do either: strips share a
  slug and a date, and a published strip's content must not change.

### 5. Rollout

1. **Continuity proof, before the PR.** Every TinyView feed was regenerated from the
   branch's data into a scratch directory and compared with the committed feeds.
   Across the 36 committed items, none changed guid, title, pubDate, isPermaLink or
   link, and none was dropped. The only difference was Bella Part 4's description,
   which lost its sibling panels. No dormant feed was written.
2. **Live listing probe, before merge.** This used the TinyView profile and wrote
   nothing. It found 449 listed, 372 already recorded, 0 non-strip links and 77 to
   catch up. Three old strips fetched live each came back with a full panel set: the
   panel count from their `index.json` plus the cover image the scraper keeps.
3. **Watched catch-up, right after merge** (plan U6). It was run by hand between
   Pass 2 and Pass 1, and the operator previewed the XML before it was committed. It recorded 78 strips, one of them posted after the probe, and
   logged `Listed but not recorded: 0`. The day's file already held 5 strips from
   Pass 1, so it ended with 83. All 78 strips matched the panel count in their
   `cdn.tinyview.com/<folder>/index.json`, and 22 feeds were written. Live on
   `origin/main`:
   - `graphic-rage.xml` returned 200; it is that comic's first feed.
   - `kowal-comics.xml` has 28 items, including Bella Parts 1-5.
   - `nick-anderson.xml` has 58 items.
   - `fowl-language-tinyview.xml` has 48 items.

   The catch-up data and feeds went in as a separate `chore:` commit.
4. **Preview against what subscribers already have**, with `scripts/preview_feeds.py`
   (PR #213):

```bash
python scripts/preview_feeds.py public/feeds --against origin/main --open
# or just the feeds you touched:
python scripts/preview_feeds.py public/feeds/kowal-comics.xml public/feeds/nick-anderson.xml --against origin/main -o /tmp/tv.html
```

   The page renders every item with its images. It flags duplicate or missing guids,
   bad dates, items out of order and items with no image. It marks each item new,
   changed, description-only or missing compared with the reference.
   `IDENTITY_FIELDS` (`scripts/preview_feeds.py:38`) are the fields a subscriber sees
   as a re-delivery. The catch-up check came back with 0 errors, 0 missing items and
   0 changed identity fields.

## Why This Works

**The root cause was two parts composed.** The scraper saves each strip once: it
skips anything already recorded, so each night's file holds only that night's new
strips. The generator read only the newest file, and `generate_feed` rewrites the
whole feed (`comiccaster/feed_generator.py:382`). Together, each feed was rebuilt
from the newest night's strips. Neither part is wrong alone, which is why checking
each part in isolation didn't find it. The generator now reads the same history the
scraper assumes exists.

**Each scraper defect had one wrong key, and the address replaces each one:**

| Defect | Before #212 | Now |
|---|---|---|
| (a) 30-90-day strips fail | `fetch_comic_page` re-listed with `days_back=30` and looked the strip up by date. The listing had covered 90 days. | Fetched by listed address; no second listing load |
| (b) Siblings collapse | The first strip with a matching date won, and "recorded" was the set of dates saved for each slug | Recorded, fetched and deduped by canonical address |
| (c) Sibling panels leak in | Any `cdn.tinyview.com` image under `<slug>/<date>` was kept, and the wait's CSS selector missed `/_next/image` srcs | `image_belongs_to_strip` on the strip's own folder, with proxy srcs unwrapped |

**Why the window uses strip dates and is anchored on the data:**

- *Not a count of files.* There are 317 TinyView data files. Twelve of them are
  empty `[]`, and outages left gaps. A strip first caught up today but dated nearly
  90 days ago would stay in a 90-file window until about 180 days after it posted. Strip dates
  measure what subscribers care about.
- *Not the clock.* After a rejected push, pipeline recovery regenerates every feed.
  With the window anchored on the newest data file, the same data gives the same
  feeds on any host at any hour.
- *Earliest usable copy wins*, so a published item never swaps its content for a
  later copy.
- *Ordered by (strip date, address)*, so same-date siblings come out in one fixed
  order whichever file saved them first. `generate_feed` sorts by pubDate only
  (`feed_generator.py:368`), and Python's sort is stable, so ties keep the order they
  arrive in.

**Why not the Comics Kingdom shape (dedup by image).** Dedup by image across a
file-count window is what caused #207, where Comics Kingdom rolled a repeated image
forward one day each night and re-delivered an old strip. PR #217 fixed that by
dating each image set from its first sighting in all saved history
(`docs/solutions/logic-errors/comicskingdom-feeds-redelivered-aging-strips.md`). A
TinyView strip's address never changes, so deduping by address has nothing to roll.

**Why not `update_feed`.** It carries the old entries over but drops every entry
that shares the new entry's date (`feed_generator.py:321`). Same-date siblings are
exactly the case this fix exists for.

## Prevention

- **Check any plan row that says "no change needed" against the code.** Open the
  function and read what it loads. The #113 row stood for five months because it
  looked like research. A plan's claims about current behavior need the same
  measurement as a bug diagnosis.
- **A strip's identity is its address, never its date and never its feed slug.**
  Take the CDN folder from the address. Pinned by:
  - `tests/test_tinyview_strips.py`: `test_folder_comes_from_the_address_not_the_feed_slug`
    (`:42`), `test_same_date_sibling_panel_does_not_belong` (`:68`),
    `test_strip_whose_name_prefixes_a_sibling_does_not_claim_its_images` (`:81`)
  - `tests/test_tinyview_scraper_local_authenticated.py`:
    `test_strips_sharing_a_date_are_recorded_separately` (`:201`),
    `test_same_date_siblings_of_a_recorded_strip_are_each_scraped_and_recorded`
    (`:249`), `test_an_unrecorded_strip_sixty_days_old_is_scraped_by_its_address`
    (`:285`)
  - `tests/test_tinyview_scraper.py`:
    `test_same_date_strips_fetched_by_address_each_keep_their_own_panels` (`:812`),
    `test_panel_wait_recognizes_proxied_panels` (`:907`),
    `test_third_positional_argument_never_becomes_the_address` (`:925`)
  - `tests/test_generate_tinyview_feeds.py`:
    `test_fowl_language_strip_keeps_its_images` (`:423`)
- **Assert on feed length, not only on scrape counts.**
  `test_three_daily_files_each_adding_a_strip_give_three_items_newest_first`
  (`tests/test_generate_tinyview_feeds.py:142`) is the test that would have caught
  #211. The window rules are pinned by
  `test_strip_dated_on_the_window_start_but_saved_in_an_earlier_named_file_is_included`
  (`:193`), `test_window_is_anchored_on_the_newest_data_file_not_the_clock` (`:210`)
  and `test_same_date_siblings_come_out_in_the_same_order_whatever_order_files_are_read`
  (`:323`).
- **Measure feed continuity before shipping a generator change.** Regenerate into a
  scratch directory, then run `scripts/preview_feeds.py --against origin/main`. Any
  change to guid, title, pubDate or link reaches every subscriber as a re-delivery.
  Pinned by `test_item_fields_match_the_previous_generator_for_the_same_strip`
  (`:369`) and `test_comic_without_a_strip_in_the_window_keeps_its_feed_byte_identical`
  (`:444`).
- **After a TinyView run, check for `Listed but not recorded: 0`.** A nonzero count
  names each address, and the next run retries them. A `No comic found` line means
  something called `scrape_comic` without an address. Pinned by the
  `TestListedButNotRecorded` class (`tests/test_tinyview_scraper_local_authenticated.py:353`).
- **Same-day reruns add to the day's file.** Pinned by
  `test_a_rerun_that_finds_nothing_new_leaves_the_file_as_it_was` (`:444`) and
  `test_the_existing_record_wins_for_the_same_address` (`:452`).
- **Known residuals:**
  - **#214 (fixed).** A retry used to quit the logged-in browser the nightly script
    handed over and start a logged-out, image-less one for the rest of the run. The
    scraper now borrows that browser (`TinyviewScraper(driver=...)`): a retry
    reuses it, and a dead session raises `BrowserSessionLost`. The nightly run then
    stops, saves the strips recorded before the loss, prints `Browser session lost
    at [i/N]`, and exits 1 so the pipeline alerts. Still invisible: a login the
    server expires mid-run while the browser stays healthy, since pages keep loading
    and nothing raises.
  - **A partial first capture is permanent.** Recorded addresses are never fetched
    again, and the earliest copy wins. After a catch-up, compare each strip's image
    count with its `cdn.tinyview.com/<folder>/index.json`.

## Related

- `docs/solutions/logic-errors/comicskingdom-political-comics-never-loaded.md`: the
  guid-continuity measurement repeated here, and #207's image-dedup shape.
- `docs/solutions/logic-errors/comicskingdom-feeds-redelivered-aging-strips.md`: the
  Comics Kingdom twin of this fix (#207, PR #217), dated by first sighting.
- `docs/solutions/logic-errors/two-sources-one-feed-file-slug-collision.md`: a
  changed guid reaches subscribers as a re-delivery.
- `docs/solutions/best-practices/verify-postconditions-not-success-signals.md`:
  measure the effect, not the success message.
- `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`: why the
  TinyView count floor is 1.
- `docs/plans/2026-09-29-1307-fix-tinyview-feed-history-plan.md`: the plan for this
  fix, including the U5 continuity proof and the U6 catch-up.
