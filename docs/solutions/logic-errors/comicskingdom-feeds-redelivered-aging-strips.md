---
title: "Comics Kingdom feeds re-delivered aging strips as their oldest copy left the 90-file window"
date: 2026-10-03
category: logic-errors
module: comicskingdom
problem_type: logic_error
component: scripts/generate_comicskingdom_feeds.py / scripts/comicskingdom_scraper_individual.py
severity: high
symptoms:
  - "About 60 Comics Kingdom feed items a night (1,858 over 2026-09-01..10-01, one per affected feed) were strips subscribers already had, under a newer guid"
  - "mostly-gravy's committed 2026-10-01 feed gained guid .../mostly-gravy/2026-07-03 for an image first sighted 2026-06-29"
  - "Dormant and vintage comics re-delivered a strip every night; weekly comics once per extra night a strip stayed up"
  - "The nightly pipeline reported success throughout; nothing checked for re-delivery"
root_cause: logic_error
resolution_type: code_fix
applies_when:
  - "A source serves its newest post for any requested date, so one strip is saved under many per-date addresses"
  - "Changing a generator's feed window or deduplication scope where existing item guids must not change"
  - "Copying a date-window start (newest minus N days) from another generator"
  - "Tempted to scrape a past date, re-run a night, relabel records, or delete snapshots in saved Comics Kingdom data"
tags: [comics-kingdom, strip-identity, feed-window, dedup, guid, redelivery, append-only-history]
related_components: [scripts/preview_feeds.py, CONCEPTS.md, AGENTS.md]
related_issues: [207, 212, 216, 217, 218]
---

# Comics Kingdom feeds re-delivered aging strips as their oldest copy left the 90-file window

## Problem

Comics Kingdom feeds re-delivered strips readers already had, about 60 items a night across the CK feeds (issue #207). Comics Kingdom serves its newest post for any date, so a strip that stays up is saved again every night under a new address. The generator deduplicated images only inside its 90-file window, so whenever a strip's earliest copy left that window, the next night's copy went out as a new item.

## Symptoms

- Readers got a strip they already had, under a newer date. For example, `mostly-gravy` first showed an image on 2026-06-29. In Pass 1 commit 57faacd7d9 (2026-10-01), its feed dropped the guid `https://comicskingdom.com/mostly-gravy/2026-07-02` and gained `.../mostly-gravy/2026-07-03` for the same image. Each night the oldest copy rolled forward one day and was sent again.
- The volume was steady. Replaying the old rule over 2026-09-01..2026-10-01 gave 1,858 re-delivered items, about 60 a night, one per affected feed. The last Pass 1 before the fix (57faacd7d9) re-delivered 59.
- Dormant and vintage comics re-sent their one strip every night. Weekly comics re-sent a strip once for each extra night it had stayed up.
- It was not only the vintage feeds. When the problem was first measured on 2026-09-28, by diffing consecutive nightly feed commits, about 60 of ~150 CK feeds re-sent a strip each night (65 on 09-28, 60 on 09-27, 63 on 09-26), and about half of them were active strips such as Alice, Prince Valiant and Kevin & Kell (session history).
- Nothing alerted. Feed generation is log-only, and the invariant guard counts scraped records, not feed items.

## What Didn't Work

### Deduplicating by image inside a file-count window (the old rule)

The scraper builds each record's address, and so its guid, from the scrape date: `url = f"https://comicskingdom.com/{comic_slug}/{date_str}"` (`scripts/comicskingdom_scraper_individual.py:321`, stored as the record's `url` at `:397`). The generator before PR #217 loaded only the 90 newest files (`files_to_load = data_files[:days_back]`, pre-#217 `scripts/generate_comicskingdom_feeds.py:130`). It skipped an image set it had already seen, but only among those files (`seen_image_urls`, pre-#217 `:199`-`:235`). Image dedup was the right idea. The window it ran inside was the problem: each night the oldest file dropped out, the earliest copy of a long-running strip went with it, and the next copy, with a guid one day later, became "first".

### The first plan's window: newest minus 90 days, copied from TinyView

The first plan dated strips by first sighting but copied the TinyView generator's window start, `window_start = newest - timedelta(days=WINDOW_DAYS)` with `WINDOW_DAYS = 90` (`scripts/generate_tinyview_feeds_from_data.py:44`, `:127`). TinyView keeps the boundary day (`strip_date < window_start` is the only exclusion, `:138`), so that window covers 91 dates.

The off-by-one stayed hidden because on 2026-10-01 the 91-date window and the old 90-file window held the same files: `data/comicskingdom_2026-07-07.json` is missing, so 91 dates held 90 files. Replayed on gap-free data (newest file 2026-03-15), the 91-date window would have put back about 85 boundary-day strips that had already been sent, at rollout. It would have done the same after any night the CK scrape failed, because with no new file the anchor stays put and the window just gets one day longer. Feasibility and adversarial reviewers caught it during plan review (plan KTD3, `docs/plans/2026-10-01-0837-fix-ck-first-sighting-identity-plan.md:125`). The lesson: a date window and a file-count window agree only if you check the inclusive boundary against gap-free data. A gap in the data can hide the mismatch. TinyView keeps its 91-date window: its identity is the strip's own address, so the extra day only lengthens a feed and never re-sends anything.

### Record validation that missed the image fields

The first version of the fix checked `slug`, `url` and `date` but not the image fields. Code review of PR #217 (requirement R7) found that one record with a null image field crashed the whole run. Because every run reads all history, one bad record anywhere would have stopped every CK feed. The gap was fixed before merge, and the image-field checks are now in `check_record` (`scripts/generate_comicskingdom_feeds.py:93`-`:98`).

### Rejected: rewriting stuck feeds with their true first-sighting date

The 37 feeds with nothing first sighted in the window (32 vintage, 5 dormant) could have been rewritten once with each item's true first-sighting date. That would have re-delivered each of them one more time, so the operator chose to leave them as they are (plan Key Decisions).

## Solution

Fixed in PR #217, merged 2026-10-01, all in `scripts/generate_comicskingdom_feeds.py`.

**Identity is the feed slug plus the sorted image URLs, dated by first sighting across all saved history.** Every strictly named file is read, oldest first. The first record that holds a given key supplies the item, and later copies are ignored (`:112`-`:125`):

```python
key = (record['slug'], tuple(sorted(images)))
if key not in first_sightings:
    first_sightings[key] = (file_date, record)
```

Sorting the URLs means panel order does not create a new strip.

**The window is the 90 dates ending on the newest data file, anchored on the data rather than the clock** (`:39`-`:41`, `:107`-`:108`, `:130`):

```python
WINDOW_DAYS = 90
window_start = newest - timedelta(days=WINDOW_DAYS - 1)
...
if file_date >= window_start:
```

On gap-free data this holds exactly the 90 newest files. Rebuilding old data on any later day gives the same feed.

**A comic with nothing to list is not written.** `main()` counts it as untouched and never calls the writer (`:213`-`:216`), and `generate_feed_for_comic` also refuses to write an empty feed (`:165`-`:167`). An existing file stays byte-identical, and no new file is created. This guard is load-bearing: `ComicFeedGenerator.generate_feed` rebuilds the whole file from the entries it is given and never merges with the old file (`comiccaster/feed_generator.py:342`-`:382`).

**The generator is network-free.** The live fallback `extract_live_comicskingdom_entries` was removed along with the `requests` import. It ran for any catalog slug missing from the loaded data (pre-#217 `:19`, `:174`-`:175`) and was the only network call in any Phase 2 generator.

**Skip and warn, never stop.** Only `comicskingdom_YYYY-MM-DD.json` names are read (`DATA_FILE_NAME`, `:44`), so backup files are ignored and cannot anchor the window. A name with an impossible date is skipped with a warning (`:54`-`:57`). An unreadable file, or one that is not a list, gives `[]` with a warning naming it (`:62`-`:73`). A malformed record, including null or non-text image fields, is skipped with a warning naming its file and position (`:85`-`:98`, `:115`-`:119`). No data files at all exits 1 (`:189`-`:192`). The run summary prints Written, Untouched and Failed separately (`:226`-`:228`).

**Item fields are unchanged.** Title is `"<Name> - <date>"`, guid and link are the record `url`, pubDate is 00:00 UTC on the record date, and the description is `"Comic strip for <date>"` (`:157`-`:162`). The guid comes from `id` (`comiccaster/feed_generator.py:268`).

**Rollout proof** (2026-10-01 data, before merge). Every CK feed was regenerated to scratch and compared with its committed copy:

- 37 feeds byte-identical, 119 rewritten.
- 0 new guids, and 0 kept items with a changed guid, title, pubDate or link.
- 116 old items dropped across 113 feeds. Almost all were each feed's 2026-07-03 item, because the window holds 89 files until the 2026-10-05 file arrives (07-07 is missing). The rest were re-sent copies in `eye-lie-popeye` (07-13, 07-22) and `phantom-2040-a-new-shadow` (09-29).
- `scripts/preview_feeds.py --against origin/main` on four feeds showed 0 new and 0 changed items each. The operator approved before the PR.

**Production.** Pass 1 commit 7f61de6b4d (2026-10-02) changed 114 CK feeds with 90 new items, 0 of them re-delivered. Pass 1 commit 8f63cf2acc (2026-10-03) changed 99 feeds with 83 new items, 0 re-delivered. The generator reported Written 119 / Untouched 37 / Failed 0 both nights. Both runs ended "with FAILURES" only because of an unrelated Far Side invariant failure (#219).

## Why This Works

The root cause was that a CK guid names the night ComicCaster fetched a strip, not the strip itself. Comics Kingdom answers any date with its newest post, so a strip up for N nights is saved under N addresses. Any rule that picks "the earliest copy I can currently see" from a sliding view will pick a later copy once the real first one slides out. First sighting fixes this by computing the earliest copy over all saved history, which only ever grows. A strip's first sighting cannot move as long as history is only appended to, so its guid is the same every night. When that first sighting leaves the window, the strip leaves the feed, and no later copy can take its place, because later copies are never candidates.

GoComics never had the problem. Its record address carries the publisher's own date: the URL is built from the favorites-page date (`scripts/authenticated_scraper_secure.py:299`, page chosen by date at `:141`), and that page lists only comics that published that day. So one strip is always one address, and the GoComics generator's plain 90-file window (`scripts/generate_gocomics_feeds.py:44`, `:50`) is safe. Checked on 2026-10-01: the last 90 GoComics files held 22,693 records with 0 images under two dates, and 71 non-daily slugs appear only on their publish days.

## Prevention

### Saved Comics Kingdom history is append-only

Because identity now rests on all history, editing old CK data can move a strip's first sighting and re-deliver it. The rules:

- Never scrape a past date. CK answers with its newest post, which gets saved under the wrong date.
- Never re-run a night's scrape into `data/` after its feed has shipped. Send manual runs to another `--output-dir`.
- Never relabel records after their feed has shipped.
- Never delete snapshots.

Git shows three past edits of this kind, as data-history evidence: 8c97da6a62 (edge-city-classic relabeled across 276 files), 96f12e8205 (a restore after conflict markers reached `data/comicskingdom_2026-04-16.json`) and ced5958eeb (the 2026-02-27 file cut from 152 to 12 records).

The rule is written down, not enforced in code (the operator's call). It appears in four places: `CONCEPTS.md:84` ("Strip identity"), `AGENTS.md:84` (the `generate_*.py` line), the CK scraper's `--date` help (`scripts/comicskingdom_scraper_individual.py:451`-`:455`), and the generator's docstring (`scripts/generate_comicskingdom_feeds.py:18`-`:19`). It applies to Comics Kingdom only. GoComics Pass 2 merges and rolling or manual backfills stay safe (`CONCEPTS.md:86`).

PR #218 (part 1 of #216) records CK's own post date and may later narrow this rule. It is open and unmerged as of 2026-10-03, so the rule stands as written above.

### Verifying a change to the CK generator

1. **Regenerate every feed to scratch and compare.** `main()` takes `data_dir`, `output_dir` and `catalog_dir` (`:180`). Untouched comics are not written, so copy the committed `public/feeds/` into the scratch directory first. Then regenerate into it and compare each feed with the committed copy. Expect no new guid, no kept item with a changed guid, title, pubDate or link, untouched feeds byte-identical, and every dropped item explained.
2. **Preview** a sample with `python scripts/preview_feeds.py public/feeds/<slug>.xml --against origin/main --open`. Expect 0 new and 0 changed items.
3. **After merge, check the next Pass 1 commits for re-delivery.** For each CK feed, diff its guids against the commit's parent. For each new guid, look up its record's image set in that commit's data files, and flag it if the set was first sighted on an earlier night. Read git objects only (`git show <commit>:<path>`). Never `git fetch` while Pass 1 is running.

### Tests that guard it (`tests/test_generate_comicskingdom_feeds.py`)

- First sighting: `test_strip_saved_on_seven_nights_is_listed_once_from_its_first_night`, `test_a_later_night_holding_the_same_image_adds_no_item` (122 nights of a weekly comic, with no guid outside the earlier set allowed), `test_image_order_does_not_make_a_new_strip`, `test_item_fields_match_the_committed_feed`.
- Window: `test_window_first_day_is_inside_and_the_day_before_is_not` (`WINDOW_START = '2026-07-04'` is in, `DAY_BEFORE_WINDOW = '2026-07-03'` is out, `:256`-`:257`; this is the test that catches the 91-date off-by-one), `test_window_is_anchored_on_the_newest_data_file_not_the_clock`.
- Untouched feeds: `test_dormant_comic_keeps_its_feed_byte_identical`, `test_comic_with_nothing_in_the_window_and_no_feed_gets_no_file`, `test_slug_not_owned_by_the_ck_catalog_gets_no_feed`.
- Robustness: `test_unreadable_file_is_skipped_with_a_warning_naming_it`, `test_file_holding_an_object_is_skipped_with_a_warning_naming_it`, `test_record_missing_its_url_is_skipped_with_a_warning`, `test_malformed_record_anywhere_in_history_is_skipped_with_a_warning` (including the null-image cases), `test_file_named_with_an_impossible_date_is_skipped_with_a_warning`, `test_no_data_files_fails_the_run`, `test_backup_file_is_not_read_and_does_not_anchor_the_window`.
- Network: `test_generator_has_no_network_path`.

### Known limits

- A feed stuck re-capturing a strip it already sent now looks exactly like a dormant feed, and nothing alerts. The Untouched count in the run summary (37 today) is the only signal. Vintage feeds are tracked in #216.
- A validly named CK data file with a future date, such as one from a mistyped `--date`, would move the window and leave every feed untouched until real dates catch up. There is no guard.
- An image URL is part of the identity. If CK moves an unchanged strip to a new URL, the feed re-delivers it once. A genuine republish with the identical URL is never listed again, which is intended (plan Risks).
- Skipping an unreadable in-window file drops that day's strips. The plan estimated about 85 strips dropped and 4-13 non-daily strips re-delivered once. The operator accepted this over stopping CK generation, which would freeze all feeds with no alert.
- A feed left untouched picks up catalog edits (`name`, `author`, `is_political`) only when it next lists a strip.

### Changing what the scraper records (#216)

Any scraper change that records different image URLs for an unchanged strip re-delivers one item per affected feed, because the new URL set is a new first sighting. See the warning on #216: https://github.com/adamprime/comiccaster/issues/216#issuecomment-5933153024. Before shipping such a change, run the scratch-regeneration check above on data that includes the changed records. Expect, and accept explicitly, one new guid per affected feed.

## Related Issues

- Issue #207 (closed by PR #217); plan `docs/plans/2026-10-01-0837-fix-ck-first-sighting-identity-plan.md`.
- Issue #216 (open): vintage feeds stuck on one strip, the scraper's repeat copies and the promo-image fallback. PR #218, its first part, is open.
- `docs/solutions/logic-errors/tinyview-feed-history-collapsed-to-one-strip.md`: the precedent (#212) this fix mirrors, and where #207 was first named as the CK analogue.
- `docs/solutions/logic-errors/comicskingdom-political-comics-never-loaded.md`: same generator; its guid-continuity measurement is the method reused here.
- `docs/solutions/logic-errors/two-sources-one-feed-file-slug-collision.md`: another way a changed guid reaches subscribers as a re-delivery.
- `docs/solutions/best-practices/verify-postconditions-not-success-signals.md` and `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`: why a green pipeline proved nothing here.
- `docs/solutions/logic-errors/gocomics-favorites-page-timing.md`: the GoComics side, whose dated addresses keep merges and backfills safe.
