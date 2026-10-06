---
title: "Comics Kingdom scraper recorded the page it loaded, not the post the page displayed"
date: 2026-10-06
category: logic-errors
module: comicskingdom
problem_type: logic_error
component: scripts/comicskingdom_scraper_individual.py / scripts/generate_comicskingdom_feeds.py
severity: high
symptoms:
  - "Records were dated and addressed by the night requested, so a strip that stayed up for a week was saved under seven nightly addresses"
  - "Five political cartoonists who upload after the 03:05 run had every strip saved a night late, under the next night's address"
  - "A fallback that grabbed any comic-like div or the whole page saved a Comics Kingdom promo image for many comics on 2026-06-02 and 06-04 (30 and 34 comics; no 06-03 file exists)"
  - "The two episodic comics (Phantom 2040, Eye Lie Popeye) had saved junk images since January"
  - "Saved names came from the page title, whose date belongs to the 10th-newest post"
root_cause: logic_error
resolution_type: code_fix
applies_when:
  - "Changing what the Comics Kingdom scraper records, or how the CK generator identifies a strip"
  - "Scraping any source whose dated page shows the newest post on or before the requested date"
  - "Switching a feed's item identity while existing items must keep their guids"
  - "Checking a CK night's feed diff for re-sends"
tags: [comics-kingdom, strip-identity, next-data, post-date, guid, redelivery, identity-switch, late-uploaders]
related_components: [CONCEPTS.md, scripts/check_scrape_counts.py, scripts/preview_feeds.py]
related_issues: [207, 216, 218]
---

# Comics Kingdom scraper recorded the page it loaded, not the post the page displayed

## Problem

For each comic, the Comics Kingdom scraper loaded `/<slug>/<run date>` and saved whatever images it could find there. It labeled them with the date it had asked for. A Comics Kingdom dated page does not show "the strip for that date". It shows the newest post *on or before* that date. So the scraper's records named the wrong date for every dormant, weekly, vintage and late-uploading comic, and its image scraping could pick up things that were not the strip at all. Issue #216, fixed by PR #218 (part 1 of the plan).

## Symptoms

- Every record's `date` and `url` were the night requested, never the post's. A strip that stayed up for a week was saved seven times under seven addresses. #207's first-sighting rule (see the related doc) made that harmless for feeds, but only by deduplicating on image sets.
- David M. Hitch, Jimmy Margulies, Lee Judge, Mike Smith and John Branch post after the 03:05 run. On 09-29 through 10-01 each of them showed a new strip dated the day before. The old format therefore saved every one of their strips a night late, under the next night's address.
- The DOM fallback (any `wp.comicskingdom.com` image in a reader container, else any "comic"-like `div`, else the whole page) saved a Comics Kingdom promo image for many comics on 2026-06-02 and 06-04 (30 and 34 comics; no 06-03 file exists).
- Phantom 2040's 2026-10-01 record held `Dumplings.ENG_.2023-11-12.jpeg` and `Dani-image.png`; Eye Lie Popeye's held Episode 1's pages, every night.
- The saved `name` came from the page `<title>`, whose date belongs to the 10th-newest post. `CONCEPTS.md` and the scraper's `--date` help wrongly said a past-date page shows the newest post.

## What Didn't Work

- **Fixing it only in the generator (#207, PR #217).** #217 made each strip's identity its image set, dated by first sighting across all saved history. Re-sends stopped, but the records stayed wrong: late uploaders were still saved a night late, the promo-image fallback and the episodic junk stayed, and saved Comics Kingdom history became load-bearing and append-only. That doc deliberately left the scraper for #216 (session history).
- **Believing the page shows its newest post.** `CONCEPTS.md` and the `--date` help both said so. The page's own `__NEXT_DATA__` query says "newest on or before". `/zits/2026-09-15` shows the 09-15 strip. That is why a past-date backfill is safe once records carry post dates (session history).
- **`assets.panels` alone.** Some posts have only `assets.single`. Without that fallback the record count would have dropped under the guard's floor on the first night (session history).
- **"The old item always wins" at the switch.** The first identity rule let an old item keep any guid a post-dated strip also wanted. Plan reviewers caught that a late uploader's old item holds an *earlier* strip under the next night's address, so that rule would silently drop one strip per late cartoonist at rollout. The fix was the `#post` guid, decided by whether the old saved name ends in a date. That rule was tested with synthetic names; on 2026-10-01, 69 of 156 saved names were dated (session history).
- **Calling every backfill safe.** An early draft of the docs said backfilling a missed night became safe. Reviewers showed that backfilling a night from *before* the switch re-sends the late uploaders' strips under their post dates. The docs now limit it to nights on or after the first post-dated file (session history).
- **Probing the site anonymously.** Comics Kingdom returned 429 after about 80 anonymous requests. Research stopped there; the logged-in profile confirmed the nightly path (session history).

## Solution

### Read the displayed post from `__NEXT_DATA__`

Each dated page embeds the query it ran (`scripts/comicskingdom_scraper_individual.py:321-390`, `extract_displayed_post`). Under `props.pageProps.fallback`, take the `ck_comic` query whose key names `ck_feature:"<source slug>"` and `before_ymd:"<requested date>"`. Its first result is the post on screen.

- Match the key on those two fields only. Never match on `per_page`, which is 10 for strips and 1 for episodic comics. Never match on the post's own slug either: vintage posts carry another feature's prefix (`beetle-bailey-1-1967-10-01` belongs to `beetle-bailey-vintage`).
- `post_date` is the date part of the post's `date`, cross-checked against the date in its `link`. A post dated after the requested night (premium early access) is rejected.
- Images are `assets.panels` in order, else `assets.single`, never `featured` (a 500×500 thumbnail). A post with neither is not recorded, and the reason is printed.
- A page with no matching query (404, firewall page, layout change) records nothing and names the reason. Nothing is read from the rendered DOM, so the promo-image fallback is gone.

### Records gain fields; existing ones keep their meaning

New records add `post_date` and `post_url` (rewritten from `wp.comicskingdom.com` to `comicskingdom.com`). `date` and `url` still mean the night requested and the page loaded, so `check_record`, the file-date invariant and a revert keep working. Every displayed post is recorded every night, repeats included, so the guard's count of about 156 stays meaningful against its floor (`scripts/check_scrape_counts.py`). The run prints greppable totals (`comicskingdom_scraper_individual.py:511-516`):

```
Recorded: 155 of 156
Repeats: 68
Not recorded: 1
  - phantom-2040-a-new-shadow: no query for phantom-2040-a-new-shadow on 2026-10-06
```

A repeat is a record whose (slug, post_date) an earlier data file already holds. Repeats are a subset of Recorded. A post dated before tonight can still be new, because late uploaders' strips first appear the night after their post date.

### The generator identifies a strip by comic and post date

`scripts/generate_comicskingdom_feeds.py:131-179` (`load_window_strips`) reads every saved file oldest first and splits records by shape:

- A record with `post_date` is one strip per (slug, post_date). It is listed when its post date is in the 90-date window, dated by its post date, under the guid and link `https://comicskingdom.com/<source slug>/<post date>`. The earliest file's copy supplies the images, so a published item never changes when Comics Kingdom later renames its images to `-WxH` copies or fills in panels.
- A record without `post_date` keeps #207's first-sighting rule.
- A malformed `post_date` is skipped with a warning, never read as an old record, because that would create a new first sighting.

### The switch: `#post` for strips an old record saved a night late

At the switch, an old item and a post-dated item can share a guid. `feed_entries` (`generate_comicskingdom_feeds.py:208-238`) decides by the old record's saved `name`, never by image sets, because renames and late-filled panels make one strip's sets differ:

- No trailing date in the old name: the old page had a post of its own that night, so they are the same strip. The old item stands, byte-identical.
- A trailing date: the old item holds an earlier strip saved a night late. The post-dated strip is listed too, under its guid plus `#post`.

The first post-dated file is `data/comicskingdom_2026-10-04.json`. `CONCEPTS.md` ("Strip identity") holds the narrowed history rule: old files stay append-only until the last of them leaves the window, so the rule lapses with the 2027-01-01 run.

## Why This Works

Comics Kingdom already says which post it displays, and each feature has at most one post per date. The post's date is therefore a stable identity, where image URLs are not: Comics Kingdom renames a post's images some days after posting, and the originals still resolve. Recording the post's own date removes the off-by-one for late uploaders and the seven-addresses-per-strip problem at the source, rather than deduplicating them after the fact. Reading embedded JSON instead of the rendered page means a layout change produces "no query" and a named reason, not a promo image saved as a strip.

## Prevention

### Measure the switch before merging it

U5 of the plan ran the branch's scraper into a scratch output directory right after a Pass 1, compared every comic with that night's committed data, then regenerated scratch feeds and previewed them `--against origin/main`. It predicted exactly the switch night's re-sends: 6 strips, 5 of them `#post` late uploaders. Production matched that count exactly. Do the same for any change to what the CK scraper records or how its generator builds guids.

### Watch results

| Night | Pass 1 commit | Recorded | Repeats | New CK items | Re-sends |
|---|---|---|---|---|---|
| 2026-10-04 (switch) | 5690d5cf79 | 155/156 | 0 | 91 | 6, all predicted |
| 2026-10-05 | 5593c5cb3b | 155/156 | 67 | 88 | 0 |
| 2026-10-06 | 959f4851f7 | 155/156 | 68 | 87 | 0 |

- The switch night's 6: `#post` items for david-m-hitch, jimmy-margulies, john-branch, lee-judge (all 2026-09-30) and mike-smith (2026-10-02), plus kirk-walters/2026-09-25.
- Every record on all three nights carried `post_date`. The one unrecorded comic was Phantom 2040: A New Shadow, whose last saved record (2026-10-03) was named "20 – FINALE". The series appears to have ended, but that name came from the old title-derived field.
- Repeats is 0 on the switch night because no earlier file held post dates. About 67 a night afterwards is the dormant, vintage and not-yet-updated comics, and is expected.

### Checking a night for re-sends

Diff each CK feed's guids against the Pass 1 commit's parent, using git objects only. Never `git fetch` while Pass 1 runs. A new guid is a re-send only when an earlier data file already holds that comic and post date.

- Match on **(slug, post_date)**. Do not match on a saved `url`. `url` is the page loaded, `/<slug>/<run date>`, which equals the next post's guid whenever a cartoonist posts that day. The 2026-10-06 check falsely flagged hitch, margulies, judge and smith that way: their 2026-10-05 strips were new posts with new images.
- Bringing Up Father's `post_url` uses `/vintage/<slug>/` while its guid uses `/<slug>/`, so compare dates, not `post_url` strings.

### Don't rewrite history before the lapse date

Until the 2027-01-01 run, never overwrite, relabel or delete a Comics Kingdom data file, and never re-run a night's scrape into `data/`. Backfilling a missing night is safe only for nights on or after 2026-10-04, and should happen the next day. `CONCEPTS.md` ("Strip identity") is the authority.

### Tests

`tests/test_comicskingdom_scraper.py` covers the extraction: panels versus single, never featured; a query for another feature or date ignored; vintage ownership through the query key; early access rejected; 404 pages; and the run totals. `tests/test_generate_comicskingdom_feeds.py` covers the merge night staying byte-identical, repeats listing nothing, window edges, source-slug addressing, `#post` for late sightings and malformed post dates.

## Related Issues

- Issue #216: this fix is part 1 (PR #218, merged 2026-10-03). Part 2 (vintage reruns) is not started; it is planned in `docs/plans/2026-10-01-1213-fix-ck-own-post-and-vintage-reruns-plan.md`.
- `docs/solutions/logic-errors/comicskingdom-feeds-redelivered-aging-strips.md` (#207, PR #217): the generator-side fix this builds on. It holds the first-sighting rule that old records still follow, append-only history, and the scratch-regeneration check reused here.
- `docs/solutions/logic-errors/comicskingdom-political-comics-never-loaded.md`: the political cartoonists whose late uploads produced the `#post` items.
- `docs/solutions/logic-errors/tinyview-feed-history-collapsed-to-one-strip.md`: the TinyView precedent, where identity is the strip's own address, not the night it was seen.
- `docs/solutions/logic-errors/gocomics-favorites-page-timing.md`: GoComics' version of late political publishers. GoComics addresses carry the publisher's date, the property CK records now have.
- `docs/solutions/best-practices/verify-postconditions-not-success-signals.md`: why the watch measured feed diffs rather than trusting a green run.
