---
title: "Comics Kingdom's political-tab comics were never loaded by either CK script"
date: 2026-09-29
category: logic-errors
module: comicskingdom
problem_type: logic_error
component: comicskingdom_scraper_individual.py / generate_comicskingdom_feeds.py / comiccaster/comicskingdom_catalog.py
severity: high
symptoms:
  - "Six Comics Kingdom political cartoonists (mike-smith, lee-judge, jimmy-margulies, david-m-hitch, ed-gamble, mike-shelton) were listed on the site's Political tab but their /feeds/<slug>.xml links 404'd"
  - "The nightly pipeline reported ALL SUCCESS every run; no failure or alert ever fired for the missing feeds"
  - "curl https://comiccaster.xyz/feeds/mike-smith.xml and lee-judge.xml returned HTTP 404"
  - "The one earlier report (Mallard Fillmore, March 2026) was closed by duplicating its entry into comics_list.json, which hid the loader gap"
root_cause: logic_error
resolution_type: code_fix
applies_when:
  - "A Comics Kingdom comic appears on the site's Political tab (public/political_comics_list.json) but has no working feed"
  - "Adding or auditing a catalog loader that should read more than one catalog list file"
  - "A user report of one missing comic looks fixable by duplicating its catalog entry rather than checking what the loader actually reads"
  - "Reasoning about whether two catalog files (comics_list.json / political_comics_list.json) are both consumed by every downstream reader"
tags: [comicskingdom, catalog, political-comics, source-of-truth, silent-failure, loader, feed-generation]
stack: [python, json]
github_prs: [208]
---

## TL;DR

Every catalog file in `public/` is two things at once: a **website tab**, and an
**input that some Source's loaders may or may not read**. The Comics Kingdom
scraper and generator each read only `comics_list.json`. Six Comics Kingdom
editorial cartoonists lived only in `political_comics_list.json`, so the
Political tab showed them with subscribe links that 404'd. They had never been
scraped, not once, in the ten months they were listed. Nothing alerted, because
nothing asserted that a listed comic has a loader.

PR #208 moved both scripts onto one shared loader that reads both lists, put
each comic in exactly one list, and added tests that fail when any Comics
Kingdom entry in any list is not loaded exactly once.

**If a comic on the site has no feed, fix the loader, not the catalog.** Copying
the entry into the list the loader happens to read makes the report go away and
keeps the bug. That is what happened in March.

## Problem

### Root cause, in two layers

**1. The loaders read one of the two lists.** Before PR #208, the scraper's
`load_comics_catalog()` and the generator's `load_comics_list()` were
near-copies of each other:

```python
catalog_path = Path('public/comics_list.json')
...
ck_comics = [c for c in all_comics if c.get('source') == 'comicskingdom']
```

Nothing on the Comics Kingdom side opened `political_comics_list.json`. The
GoComics generator had read both lists for a long time
(`scripts/generate_gocomics_feeds.py:118-135`). The Comics Kingdom scripts never
did.

**2. A catalog file doesn't say who reads it.** `public/index.html:258-272`
builds the Daily tab from `comics_list.json` + `tinyview_comics_list.json` and
the Political tab from `political_comics_list.json`. So a `source:
comicskingdom` entry added to the political list *looked* finished: it rendered
on the site with a subscribe link built from its slug. Whether a scraper would
ever visit it depended on code the JSON file gives no hint of.

Neither layer shows up on its own. The loaders looked right if you checked them
against the daily list, and that is the only list anyone checked them against.
The catalog looked right if you checked the website.

Affected: `mike-smith`, `lee-judge`, `jimmy-margulies`, `david-m-hitch`,
`ed-gamble`, `mike-shelton`, all in the political list since the 2025-11-15
Comics Kingdom import (`11e401b688`). Mallard Fillmore and Brilliant Mind of
Edison Lee would have made eight, but each also had a copy in the daily list
(see What Didn't Work).

## Symptoms

How it looked from outside:

- Six cartoonists on the Political tab. `curl
  https://comiccaster.xyz/feeds/mike-smith.xml` and `lee-judge.xml` returned
  **404**. No feed file had ever been written for any of the six.
- Every nightly run reported **ALL SUCCESS**. The count guard
  (`scripts/check_scrape_counts.py`) checks that a scrape returned close to the
  number of comics the loader handed it. It cannot see comics the loader never
  handed it: 150 loaded, ~150 scraped, green.
- No log line, no issue, no subscriber report for these six. A manual catalog
  sweep on 2026-09-28 found them by comparing Comics Kingdom's `/features` and
  `/genre/political` pages against our lists and our feed files.
- The one earlier user report, Mallard Fillmore in March 2026, was closed by a
  patch that hid the evidence (below).

## What Didn't Work

**Duplicating the entry into the list the loader reads.** A user reported
Mallard Fillmore missing. Commit `86cccece25` (2026-03-21, "Add Mallard Fillmore
to Comics Kingdom catalog": *"User-reported missing feed. Added to
comics_list.json"*) copied the political entry into the daily list. The feed
appeared, the report closed, and the loader bug survived. Brilliant Mind of
Edison Lee had been in both lists since the 2025-11-15 import, so its feed
worked by accident. Every symptom anyone reported got patched in the data. The
six comics nobody asked about stayed dark for six more months.

The copy also had a cost of its own. Mallard's daily entry had no `is_political`,
so the feed was built without the "Political Comics" category
(`comiccaster/feed_generator.py:87-88`). The feed as it stood just before the
fix has 0 occurrences of that category. Today it has 91 (the channel plus 90
items).

**An inventory that asked "who reads this file?"** The 2026-05-16 dual-catalog
plan (`docs/plans/2026-05-16-001-fix-dual-catalog-source-of-truth-plan.md`)
listed the readers of each `public/` catalog. It recorded both Comics Kingdom
scripts as readers of `comics_list.json` and held up the generator as "the
pattern to mirror". For `political_comics_list.json` it listed only the UI. That
was accurate, and it *was* the bug, but the question being asked was
per-file. The question that finds this bug is per-entry: *for each entry in this
file, does its Source's loader read it?*

**Rejected during the fix:** keep duplicating political Comics Kingdom entries
into the daily list, the way Mallard was patched. The operator's call: "we don't
need that to be dangling as a one-time exception forever."

## Solution

PR #208, merged 2026-09-28.

**1. One shared loader.** `load_comicskingdom_catalog(catalog_dir='public')` in
`comiccaster/comicskingdom_catalog.py:22`:

- reads the daily list (required) and the political list (optional; a missing
  file logs a warning and is skipped, as the GoComics loader does, `:38-46`);
- keeps `source == 'comicskingdom'` (`:52`);
- returns daily entries first, then political. A slug seen twice keeps its first
  (daily) entry and logs a warning naming both files (`:55-61`).

Both scripts call it through their old wrapper names,
`scripts/comicskingdom_scraper_individual.py:303` and
`scripts/generate_comicskingdom_feeds.py:135`, so tests that patch the wrappers
by name keep working.

**2. One list per comic.**

| Slug | Before | After | Why |
|---|---|---|---|
| `mallard-fillmore` | both | political | undoes the March copy; `author: Bruce Tinsley` carried over to the political entry |
| `brilliant-mind-of-edison-lee` | both | daily | a kids' strip, misfiled as political |
| `john-branch`, `willy-black` | daily | political | Comics Kingdom's `/genre/political` lists them; `john-branch`'s `?post_type=ck_comic&p=...` url normalized to `https://comicskingdom.com/john-branch` |

Result: 147 daily + 9 political = 156 Comics Kingdom comics.

**3. Loader change and catalog moves in one commit** (`bb42310b99`, inside PR
#208). Each half is broken alone. The moves without the loader take
`mallard-fillmore`, `john-branch` and `willy-black` out of the only list the old
loader read, so all three stop being scraped. **Revert them together.**

**4. No subscriber re-delivery.** Moved entries kept `name` exactly. Item titles
come from `name` (`scripts/generate_comicskingdom_feeds.py:157`) and guids from
the scraped per-date URL (`:162`), so moving an entry between lists changes
neither. This was measured, not assumed: regenerating the four moved feeds gave
identical guid+title sets (90 / 16 / 14 / 90 items).

**5. Tests.** All offline and in the default run. The 11 guard tests were red on
the old code, each for its stated reason, before the fix went in.

- `tests/test_catalog_source_integrity.py`
  - `test_no_slug_is_in_both_daily_and_political_catalogs` (`:212`): each comic
    lives on one tab. `DAILY_AND_POLITICAL_ALLOWLIST` (`:163`) excuses four
    GoComics strips that are on both tabs on purpose (`doonesbury`,
    `tomthedancingbug`, `brian-mcfadden`, `think`). The allowlist only excuses a
    slug that is GoComics in *both* lists, so a Comics Kingdom slug can never be
    excused (`:259`), and an allowlisted slug that has left a list fails as stale
    (`:224`).
  - `test_every_comicskingdom_entry_is_loaded_exactly_once` (`:290`),
    parametrized over both wrappers. This is the test that would have caught the
    bug on the day the six were added:

    ```python
    expected = set(_ck_slugs(_catalog(DAILY))) | set(_ck_slugs(_catalog(POLITICAL)))
    loaded = [comic["slug"] for comic in load()]
    missing = sorted(expected - set(loaded))   # listed on the site, never scraped
    ```

  - `test_every_spanish_comicskingdom_entry_is_loaded` (`:314`): the Spanish list
    is a derived UI filter the loaders never read, so any Comics Kingdom entry
    there must be one the loaders already build. Without this, the same bug could
    come back through a third tab.
- `tests/test_generate_comicskingdom_feeds.py`: helper behavior (daily-then-
  political order, de-dup keeps the daily entry and warns, a missing political
  file warns, `:95-183`), plus a `main()` integration test (`:199`) that writes
  a political-only comic's feed, with the "Political Comics" category, with
  network access mocked.
- `tests/test_comicskingdom_scraper.py:722`: the scraper's loader includes
  every political Comics Kingdom entry, once each.

**6. Floor raised with the catalog.** `SOURCE_RULES["comicskingdom"]` in
`scripts/check_scrape_counts.py:45-46` went from 140 to 146, `"Comics Kingdom
(catalog of 156)"`. That keeps the ~94% margin that 140 of 150 gave.
`docs/STATUS.md` was updated to match.

**Verified in production** (2026-09-29 Pass 1, ALL SUCCESS):

```
📚 Loaded 156 Comics Kingdom comics from catalog (daily + political)
✅ Comics Kingdom (catalog of 156): 156 entries (minimum 146).
```

`data/comicskingdom_2026-09-29.json` has 156 entries with 156 unique slugs. All
six new slugs are present with the right art: the image filenames decode to
"ckMike Smith-ENG-...", "ckLee Judge-ENG-...", and so on. Feed files exist for all
six, and all six return 200 on the live site. The two dormant cartoonists' feeds
show their last strip.
`mallard-fillmore.xml` held 90 items before and after, with 0 duplicates.

## Why This Works

- **One function, one place to be right.** The scraper and generator can no
  longer disagree about what the catalog is. Adding a list is a change to one
  file.
- **The tests assert the property the bug broke**, against the real `public/`
  files: every Comics Kingdom entry in any list reaches both loaders, once. A
  new entry in the wrong place fails the suite the day it lands, not ten months
  later in a manual sweep.
- **One-list-per-comic is enforced by a test, not by the de-dup.** The de-dup is
  a backstop. It turns a slip into a warning instead of a double scrape, but it
  keeps the *daily* entry. A political comic that slipped into the daily list
  would quietly lose `is_political` and its "Political Comics" category, which
  is exactly what the March copy did to Mallard. The overlap test catches the
  slip before the backstop has to choose.
- **The allowlist can't hide a Comics Kingdom slug.** A shared GoComics slug is
  one feed, because the GoComics generator works from scraped data. A shared
  Comics Kingdom slug is two scrapes, because its loaders walk the catalog. The
  guard encodes that difference instead of trusting whoever edits the allowlist.

## Prevention

- **Every catalog file is a tab *and* a loader input.** When you add a catalog
  list or a Source, list every file its entries can live in (today
  `comics_list.json`, `political_comics_list.json`, `tinyview_comics_list.json`,
  `spanish_comics_list.json`, `external_comics_list.json`, and the Far Side and
  New Yorker lists). For each one, name the loader that reads it for that Source,
  or the reason none needs to. Then assert it in
  `tests/test_catalog_source_integrity.py`, following
  `test_every_comicskingdom_entry_is_loaded_exactly_once`.
- **Never fix a missing feed by duplicating a catalog entry.** "Comic X is on the
  site but has no feed" means some loader doesn't read the list X lives in. Find
  that loader. If your fix touches only JSON, it is probably the wrong fix.
- **A derived list gets a coverage test, not a loader.** The Spanish list shows
  the pattern: it is never read by a loader, and a test proves everything on it
  is built from a list that is.
- **Ask inventory questions per entry, not per file.** "Who reads this file?"
  was answered correctly in May and still missed the bug.
- **Re-derive the scrape floor when a catalog changes.** The count guard checks
  that a scrape filled the loader's list. It cannot tell you the list is short.
  Keep the catalog size in the `SOURCE_RULES` note in step.

### Catalog-list drift keeps recurring

This is the fourth time a catalog list drifted away from what one of its
consumers reads:

1. `docs/plans/2026-05-16-001-fix-dual-catalog-source-of-truth-plan.md`: the
   GoComics generator read a stale catalog copy, so catalog edits never produced
   feeds.
2. `docs/solutions/ui-bugs/spanish-ui-filter-missing-comics-source-list-mismatch.md`:
   the Spanish tab's list was not synced with `comics_list.json`.
3. `docs/solutions/logic-errors/two-sources-one-feed-file-slug-collision.md`: a
   slug claimed by two sources, so the feed flipped source twice a day.
4. This one: the Comics Kingdom loaders never read the political list.

Each time, a person found it, not a check. The shape is the same every time: a
JSON list with two consumers, the website and a Source's pipeline, and nothing
tying them together. `tests/test_catalog_source_integrity.py` is now where that
tie lives. The next catalog change should extend it rather than start a new
silo.

## Related

- Issue #207 was a separate problem, not fixed here; PR #217 fixed it later.
  Comics Kingdom serves its latest strip for any date, and the generator's
  90-file dedup window rolled a repeated image forward a day each night, so about
  60 Comics Kingdom feeds re-delivered an old strip nightly. See
  `docs/solutions/logic-errors/comicskingdom-feeds-redelivered-aging-strips.md`.
- `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md` has the
  same "ALL SUCCESS while wrong" shape. A guard can only verify the work it was
  handed, not whether it was handed all of it.
- `docs/plans/2026-09-28-1129-fix-catalog-sweep-ck-political-loader-plan.md`: the
  plan for this fix.
