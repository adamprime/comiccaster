---
title: TinyView Feed History and Strip Capture - Plan
type: fix
date: 2026-09-29
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# TinyView Feed History and Strip Capture - Plan

## Goal Capsule

- **Objective:** A TinyView subscriber gets every strip a comic publishes, including several strips filed under one date, each with its own art. A feed shows the last 90 days of strips, and nothing a subscriber already has arrives again.
- **Means:** Build each feed from the 90-day window of saved strips (KTD1-KTD4), and have the scraper identify strips by their own address instead of by date (KTD5-KTD7).
- **Authority:**
  - Requirements win on behavior, KTDs win on mechanism, and units override neither.
  - The operator's raw-XML preview approval gates the PR (U5) and the catch-up commit (U6), and the operator merges the PR.
  - `CLAUDE.md` governs git practice: explicit staging, green `pytest -v` before any push, conventional commits, code and feed data committed separately.
- **Stop and ask when:**
  - the continuity proof in U5 shows any changed guid or title, a dropped item, or a touched dormant feed (R2, R3);
  - the live check in U5 captures zero or clearly partial panels for an older strip;
  - the TinyView login fails or its Chrome profile is locked;
  - a rebase conflicts;
  - the catch-up run in U6 records far more than about 60 strips, which would mean recorded and listed addresses don't match.
- **Execution profile:**
  - U1-U5 are code in the git worktree `worktrees/tinyview-feed-history` on branch `fix/tinyview-feed-history`, shipped through a PR. The main checkout stays on `main`.
  - U6 is an operational run in the main checkout after merge, between the end of Pass 2 (13:05) and the start of Pass 1 (03:05).
  - U7 documents the fix.
- **Who finishes:** The implementing agent does U1-U7. The operator approves both previews and merges the PR.

---

## Product Contract

### Summary

Rebuild each TinyView feed from every strip saved in the last 90 days instead of only the newest night's file. Fix the scraper so it can fetch any strip it lists, records each strip by its own address, keeps only that strip's images, and adds to the day's data on a rerun. The first run after merge backfills each feed and catches up strips the scraper has been missing.

### Problem Frame

Every established TinyView feed holds exactly one item, and has since late November 2025 (issue #211). The scraper records each strip once, so a night's `data/tinyview_<date>.json` holds only that night's new strips. The generator reads only the newest file and rewrites each feed from it. The April 90-day history change (#113) left the TinyView generator alone because its plan recorded that it "already loads all files", which was never true. New subscribers see one strip, and a reader that checks less often than a comic posts misses strips.

The scraper has three more defects on the same path.

- **It can't fetch older strips.** It lists 90 days of strips, then looks each one up again in a 30-day list. Every strip 30-90 days old fails: 49 wasted page loads on 2026-09-29, about 4 extra minutes of Pass 1.
- **It loses same-date strips.** That second lookup takes the first strip matching the date, and "already recorded" is keyed on date. Kowal Comics' five-part "Bella" is filed entirely under 2026/09/24. We recorded Part 4 four times, Parts 1-3 were never captured, and Part 5 (posting 2026-09-29) would be skipped for good. About 10 strips have been lost this way since June.
- **It saves other strips' images.** Images are kept by date folder, so a strip saves same-date siblings' panels too. The saved Part 4 carries all 14 of Part 3's panels, and 7 strips in the current window are affected.

### Requirements

**Feed history**
- R1. Each TinyView feed carries every usable strip saved with a strip date in the last 90 days, not only the newest.
- R2. No existing feed item changes its guid or title, and no item already in a committed feed is dropped by the change.
- R3. A comic with no usable strip in the window keeps its feed file exactly as it is. It is never emptied, rewritten or deleted.
- R4. Each feed item shows only its own strip's images.
- R5. Rebuilding from the same saved data produces the same feed items in the same order, on any host and in pipeline recovery.

**Strip capture**
- R6. The scraper fetches every strip it lists across its 90-day listing window.
- R7. The scraper records each strip once by its own address, so every strip filed under a shared date is captured, including one posted after a sibling was recorded.
- R8. A strip whose page yields none of its own images is not recorded, so the next night retries it.
- R9. Rerunning the scraper on a day adds new strips to that day's data file instead of replacing it.

**Rollout**
- R10. Before the PR ships, a measurement on the committed data proves R2 and R3, and the operator previews the raw XML.
- R11. The backfill and catch-up are one-time effects, watched by the operator: feeds grow to up to 90 days of strips, about 49 older strips and about 10 lost same-date strips are recovered, and Graphic Rage gets its first feed.

### Key Decisions

- **Merge old strips into each feed the way GoComics and Comics Kingdom do.** Governs R1. (session-settled: user-approved — chosen over keeping one-strip feeds: the operator wants feeds to carry history like the other Sources)
- **Backfill on the first run.** Recent subscribers may see older strips they never got appear once, dated in the past. Governs R1, R11. (session-settled: user-approved — chosen over growing each feed forward from today only: history is restored at once instead of over about three months)
- **Catch up the strips 30-90 days old.** This costs one slower night and gives Graphic Rage its first feed. Governs R6, R11. (session-settled: user-approved — chosen over narrowing the listing to 30 days: those strips would never be captured)
- **Fix same-date strip loss in this PR.** Governs R4, R7. (session-settled: user-directed — chosen over a separate follow-up issue: it is the same scraper code, and Bella Part 5 would otherwise be lost)
- **One branch and PR for all of it.** (session-settled: user-approved — chosen over filing the problems for later)

### Success Criteria

- After the catch-up run, active TinyView feeds hold their last 90 days of strips. On today's data alone nick-anderson goes from 1 to 51 items and fowl-language-tinyview from 1 to 41.
- Kowal Comics' feed carries Bella Parts 1-5 as five items, each with only its own panels.
- The Pass 1 after the catch-up night reports a listed-but-unrecorded count of 0 for TinyView.

### Scope Boundaries

- The GoComics and Comics Kingdom generators, the catalogs, and `SOURCE_RULES` do not change. The TinyView minimum stays at 1: it counts strips recorded today, and a merged rerun keeps that count.
- Item titles stay the series name and item dates stay the strip's folder date, per R2 and KTD3 (item fields derived exactly as today).
- Earlier plans (`docs/plans/2026-04-15-001-feat-extend-feed-history-90-days-plan.md`, `docs/plans/2026-09-28-1129-fix-catalog-sweep-ck-political-loader-plan.md`) stay as historical records. U7's solution doc records their wrong TinyView assumptions.

#### Deferred to Follow-Up Work

- **Per-strip item titles.** Every TinyView item is titled with the series name, so same-date siblings look identical in a reader. The data already carries each strip's own title.
- **Item dates from TinyView's publish time.** Bella's parts all carry the 2026-09-24 folder date though they posted 09-26 through 09-29.
- **Alerting on TinyView generator failures.** Feed generation stays log-only pipeline-wide.
- **The Comics Kingdom generator's live-fetch fallback.** It contradicts the network-free Generate phase in `AGENTS.md`. It belongs with the #207 work.

### Sources

- Issue #211 (both problems, measured 2026-09-29).
- `docs/solutions/best-practices/catalog-sweep-and-comic-onboarding-by-source.md`: the "30-day caveat" and "Feed contents" bullets document today's behavior.
- `docs/solutions/logic-errors/comicskingdom-political-comics-never-loaded.md`: the guid-continuity measurement to repeat here, and the Comics Kingdom image-dedup shape not to copy (#207).
- `docs/solutions/logic-errors/two-sources-one-feed-file-slug-collision.md`: a changed guid re-delivers every item, and the pipeline reports success regardless.
- `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`: the TinyView minimum of 1 and why not to raise it.
- `docs/solutions/best-practices/verify-postconditions-not-success-signals.md`: prove the effect in the subscriber-facing XML, not in mocks.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **The window goes by strip date, anchored on the newest dated data file.**
  - Keep a strip when its date falls within 90 days of the newest strictly named `data/tinyview_YYYY-MM-DD.json`. The boundary day counts as inside.
  - Skip data files named before the window start. A strip is never dated after the file that saved it.
  - Counting files, as GoComics and Comics Kingdom do, doesn't fit TinyView. The 317 files include 12 empty ones and outage gaps, and a caught-up strip would linger for up to about 180 days.
  - The strict name match excludes `data/tinyview_2025-11-16_backup.json`. Anchoring on the data instead of the clock keeps recovery regeneration deterministic (R5).
  - Legacy `YYYY/MM/DD` strip dates are normalized. An unreadable file or record is skipped with a warning.
- KTD2. **Deduplicate by canonical strip address, and the earliest-recorded copy wins.**
  - Files are read oldest to newest, so a published item's content never swaps for a later copy.
  - Entries are ordered by strip date, then address, before the feed is built. Same-date siblings share a timestamp, and `generate_feed` keeps input order for ties (R5).
  - Deduplicating on images, as the Comics Kingdom generator does, is what causes #207's rolling re-delivery, so it is not copied.
- KTD3. **Item fields are derived exactly as today.**
  - The guid is the strip address, with no `id` set. The title is the entry's `name`. `pub_date` is the strip date at 23:59:59 UTC. Entries without images are skipped.
  - The feed is written with `ComicFeedGenerator.generate_feed`. `update_feed` would collapse same-date strips into one item.
- KTD4. **Only comics with at least one usable strip in the window are written.**
  - Every other feed file is left untouched, as the GoComics generator does. That covers the 13 dormant feeds whose 2025 placeholder items the data can't reproduce (R3).
  - "Usable" means after the image filter (R4). A comic whose strips all lose their images counts as having none, so a 0-item feed is never written.
- KTD5. **One strip-identity helper serves both the scraper and the generator.** It lives in a small Selenium-free module in the `comiccaster` package, like `comiccaster/comicskingdom_catalog.py`.
  - **Canonical address:** scheme, host and path, with no query, fragment or trailing slash. This is a no-op on all 392 addresses in the current window.
  - **Strip folder:** the address path `<series>/<YYYY>/<MM>/<DD>/<strip>`, taken from the address. The feed slug can't be used: `fowl-language-tinyview` is filed at `fowl-language` on TinyView, and deriving from the slug would drop every Fowl Language image.
  - **Image rule:** an image belongs to a strip only when it sits under that strip's folder on `cdn.tinyview.com`. All 2,317 saved strips keep at least one image under this rule.
  - An address without the strip segment is not a strip.
- KTD6. **The scraper fetches each strip by its listed address.**
  - `scrape_comic` and `fetch_comic_page` take the address as a new keyword-only argument. `BaseScraper`'s abstract signatures stay as they are. `tinyview_scraper.py`'s `main()` and `legacy_scripts/test_tinyview.py` already pass a third positional argument, and it must not bind to the new one.
  - With an address, there is no second listing load. Without one, the date lookup stays, and its window becomes the listing's 90 days.
  - Image extraction, the panel-load wait, and the `data-src` fallback all use the strip folder (KTD5).
  - With no own images found, `scrape_comic` returns nothing (R8).
- KTD7. **"Already recorded" is the set of canonical addresses in every saved data file.**
  - The nightly script dedupes the listing by canonical address and records the listed address, not the browser's final URL.
  - It logs how many listed strips it didn't record, and which ones. This count is the run's check that every listed strip was captured (R6), since fetching by address never reaches the date lookup that logs "No comic found".
  - A rerun on the same day merges into today's file keyed by address, and the existing record wins. `merge_with_existing` in `scripts/authenticated_scraper_secure.py` is the precedent.
- KTD8. **The catch-up runs once, by hand, with the operator watching, after merge.**
  - It is a manual TinyView scrape and generate in the main checkout between 13:05 and 03:05. The operator previews the new and changed XML before it is committed, as with the 2026-09-28 new-comic feeds.
  - The operator merges only after Pass 2 (13:05), on a day when U6 and its preview can finish before the operator stops for the night, and U6 starts as soon as the merge lands. Pass 1 begins with `git reset --hard origin/main`, which discards an uncommitted catch-up, so an evening merge with no time to preview skips the preview.
  - If U6 still misses the window, the next Pass 1 does the catch-up unattended, and U6's checks run the next morning instead.

### Risks

| Risk | Mitigation |
|---|---|
| Listed and recorded addresses differ in shape, so every listed strip looks new and the run re-scrapes hundreds of pages. | Both sides go through the KTD5 canonical form. U6 stops if the catch-up records far more than about 60 strips. |
| Pages for strips 30-90 days old have never been fetched, and may render partially, freezing a partial capture. | The panel wait keys on the strip's own folder (KTD6). U5 fetches three such strips live before merge. |
| The backfill shows recent subscribers older strips as unread. | Accepted (Key Decisions). Guids are unchanged, so nobody gets a repeat. |
| About 21 TinyView feeds are rewritten every night, because `lastBuildDate` changes. | Accepted, as with GoComics and Comics Kingdom. Items only change when data changes. |
| Regenerated XML left in `public/feeds/` is swept into the next pipeline commit. | U5 regenerates into a scratch directory. U6 runs after Pass 2 and commits before Pass 1. |

---

## Implementation Units

### U1. Strip identity helper

- **Goal:** One definition of a TinyView strip's canonical address, its CDN folder, and which images belong to it.
- **Requirements:** R4, R7, R8.
- **Dependencies:** none.
- **Files:**
  - Create `comiccaster/tinyview_strips.py`.
  - Test `tests/test_tinyview_strips.py`.
- **Approach:**
  1. Implement KTD5's three rules as pure functions with no Selenium or network imports, so the network-free generator can use them.
  2. Take the folder from the address path only.
- **Execution note:** Implement test-first.
- **Patterns to follow:** `comiccaster/comicskingdom_catalog.py` (a small shared module used by a scraper and a generator).
- **Test scenarios:**
  - A strip address with a query, fragment or trailing slash canonicalizes to the plain address. The canonical form of an already-canonical address is unchanged.
  - The `fowl-language-tinyview` strip address `https://tinyview.com/fowl-language/2026/09/27/cutting-edge` yields the folder `fowl-language/2026/09/27/cutting-edge`, and its panel image under that folder on `cdn.tinyview.com` belongs to it.
  - For Kowal's `bella-part-4-of-5`, a `bella-part-3-of-5` panel does not belong, and the series cover image inside the Part 4 folder does.
  - An image with the right folder on another host does not belong.
  - An address with only a date and no strip segment is not a strip.
- **Verification:** The helper's tests pass, and nothing in it imports Selenium.

### U2. Generator builds each feed from the 90-day strip window

- **Goal:** `scripts/generate_tinyview_feeds_from_data.py` builds each TinyView feed from every usable strip in the window.
- **Requirements:** R1, R2, R3, R4, R5; KTD1-KTD4.
- **Dependencies:** U1.
- **Files:**
  - Modify `scripts/generate_tinyview_feeds_from_data.py`.
  - Test `tests/test_generate_tinyview_feeds.py` (new).
- **Approach:**
  1. Replace the newest-file read with the KTD1 window load.
  2. Apply KTD2's dedup and ordering, and filter each strip's images with U1.
  3. Hand the result to `generate_feed` for each comic with usable strips (KTD3, KTD4).
  4. Let the data and output directories be passed in, defaulting to `data` and `public/feeds`, so tests and U5's scratch run need no chdir tricks. The pipeline command line doesn't change.
- **Execution note:** Implement test-first. There are no tests for this generator today.
- **Patterns to follow:**
  - The `tmp_path` fixtures in `tests/test_generate_gocomics_feeds.py`.
  - The `main()` integration test in `tests/test_generate_comicskingdom_feeds.py`, which writes feeds under `tmp_path`.
- **Test scenarios:**
  - Three daily files each holding one new strip for a comic produce a feed with all three items, newest first.
  - A strip dated exactly 90 days before the newest file is included. One dated 91 days before is not.
  - A `tinyview_2025-11-16_backup.json` file and an empty `[]` file are ignored without error. A malformed file is skipped with a warning and the other feeds still build.
  - A legacy `YYYY/MM/DD` strip date inside the window is included.
  - A strip saved in two files keeps the older file's copy. Four identical copies in one file give one item.
  - Two strips on the same date come out in the same order on every run, whatever order their files are read in.
  - The item guid, title and `pub_date` for a strip equal what the current generator produces for it.
  - A saved strip carrying a sibling's images yields an item with only its own images.
  - A `fowl-language-tinyview` strip keeps its images.
  - A catalog comic with no strip in the window leaves its existing feed file byte-identical, and creates none if it had no file.
  - A comic whose only strip has no usable images is treated as having no strip, and its existing file is untouched.
  - A strip for a slug missing from the catalog is skipped, and other feeds build.
- **Verification:** The new tests pass, and running the generator against a copy of the real data changes no guid or title (proved in full in U5).

### U3. Scraper fetches each strip by its own address

- **Goal:** `comiccaster/tinyview_scraper.py` fetches a strip from the address it was listed under and saves only that strip's images.
- **Requirements:** R4, R6, R8; KTD5, KTD6.
- **Dependencies:** U1.
- **Files:**
  - Modify `comiccaster/tinyview_scraper.py`.
  - Test `tests/test_tinyview_scraper.py`.
- **Approach:**
  1. Add KTD6's keyword-only address argument to `scrape_comic` and `fetch_comic_page`, and pass it through.
  2. Switch the three image-matching sites (extraction, panel wait, `data-src` fallback) to U1's rule.
  3. Change the fallback lookup's 30-day window to the listing's 90.
  4. `test_mixed_image_sources_filtering` asserts the sibling capture being removed, and `test_tinyview_url_construction` asserts a listing load first. Update both on purpose, each with a comment saying why, so nobody restores the old behavior.
- **Execution note:** Write the failing scenarios first. Selenium stays mocked, as the existing tests do.
- **Patterns to follow:** The mocked-driver tests already in `tests/test_tinyview_scraper.py`.
- **Test scenarios:**
  - Given an address, the driver loads that strip page directly and never loads the series listing page.
  - Two strips listed under one date, fetched by address, each return their own address and images.
  - A page containing a sibling strip's panels yields only the requested strip's panels, through both the `src` path and the `data-src` fallback.
  - A strip page with no images under its own folder makes `scrape_comic` return nothing.
  - Called without an address, the old date lookup still works, and finds a strip 60 days old.
  - A call with a third positional argument, the way `main()` makes it, does not set the address.
  - A driver exception still yields nothing, as today.
- **Verification:** The scraper tests pass, including the two updated ones, with no live network access.

### U4. Nightly scrape records strips by address and merges reruns

- **Goal:** `scripts/tinyview_scraper_local_authenticated.py` decides "already recorded" by address, fetches each new strip by address, and adds to today's file on a rerun.
- **Requirements:** R6, R7, R8, R9; KTD7.
- **Dependencies:** U1, U3.
- **Files:**
  - Modify `scripts/tinyview_scraper_local_authenticated.py`.
  - Test `tests/test_tinyview_scraper_local_authenticated.py` (new).
- **Approach:**
  1. Build the recorded set from the canonical addresses in every saved file, including the backup file, which only adds addresses.
  2. Dedupe the listing and skip recorded addresses.
  3. Pass each strip's address to `scrape_comic`, and record the listed canonical address.
  4. Log the count and addresses of listed but unrecorded strips.
  5. Merge into an existing file for today, keyed by address, with the existing record winning.
- **Execution note:** Implement test-first against a stub scraper object; nothing here needs a browser.
- **Patterns to follow:**
  - `merge_with_existing` in `scripts/authenticated_scraper_secure.py`.
  - The `sys.path` shim used by `tests/test_comicskingdom_scraper.py` to import a script.
- **Test scenarios:**
  - With one strip dated 2026-09-24 recorded, a listing of five strips on that date scrapes the four unrecorded ones and records each under its own address.
  - A listing that repeats a strip, including once with a `#comments` fragment, scrapes it once.
  - A listed strip already recorded in any saved file, including the backup file, is not scraped.
  - A strip 60 days old that is unrecorded is scraped by address.
  - A strip for which `scrape_comic` returns nothing is not recorded, and is counted in the unrecorded log line.
  - A rerun on a day whose file already holds strip A, finding new strip B, leaves the file with both, and A's record is unchanged.
  - A rerun that finds nothing new leaves today's file as it was, so the invariant guard still sees its strips.
- **Verification:** The new tests pass, and the script's command-line use by `scripts/local_master_update.sh` is unchanged.

### U5. Pre-ship proof, preview and PR

- **Goal:** Measured proof that the change is safe for subscribers, operator approval of the XML, and a PR.
- **Requirements:** R2, R3, R10; KTD8.
- **Dependencies:** U2, U3, U4.
- **Files:** none in the repo. Scratch output lives in the session scratchpad.
- **Approach:**
  1. **Continuity proof.** Regenerate every TinyView feed from the branch's data into a scratch directory, and compare it with the committed `public/feeds/*.xml`. Ignore `lastBuildDate`. Check four things:
     - every committed item's guid and title is present and unchanged;
     - no committed item is dropped;
     - the dormant feeds and any feed without in-window strips were not written;
     - description changes are limited to the 7 strips carrying a sibling's images.
  2. **Live check.** Outside the pipeline windows, with no pipeline run using the TinyView Chrome profile, fetch Bella Part 1, one July Skull Pizza strip and Graphic Rage's 2026-07-13 strip with the new scraper code. Confirm each yields its full own panel set, and write nothing into `data/`.
  3. **Preview.** Send the operator the raw XML of `nick-anderson`, `fowl-language-tinyview` and `kowal-comics` from the scratch run.
  4. **Ship.** After a green full suite, open the PR. The merge follows KTD8's timing rule.
- **Test expectation:** none -- this unit verifies U2-U4 on real data and ships them.
- **Verification:** The continuity proof reports zero guid or title changes, zero dropped items, and zero dormant writes. The live check shows full panel sets, the operator approves the preview, and the PR's CI is green.

### U6. Watched catch-up run after merge

- **Goal:** The one-time backfill and catch-up happen once, in the open, and are committed only after the operator has seen them.
- **Requirements:** R11; KTD8.
- **Dependencies:** U5 merged.
- **Files:** `data/tinyview_<date>.json` and TinyView `public/feeds/*.xml`, as data, not code.
- **Approach:**
  1. In the main checkout on a clean, current `main`, after 13:05 and well before 03:05, run the TinyView scraper and generator by hand.
  2. Check the recorded count is about 60, not hundreds, and that the listed-but-unrecorded count (KTD7) is 0. A nonzero count names each strip, and the operator decides whether to stop before committing.
  3. Send the operator the raw XML of `graphic-rage` (a new feed) and `kowal-comics` (Bella Parts 1-5).
  4. On approval, commit the data file and the regenerated TinyView feeds in one `chore:` commit, staging explicit paths, and push.
  5. The next morning, confirm Pass 1 recorded only that night's new strips, reported a listed-but-unrecorded count of 0, and opened no TinyView invariant issue.
- **Test expectation:** none -- an operational run, verified by the checks in the Approach.
- **Verification:** The catch-up commit is on `origin/main`, and `graphic-rage.xml` serves HTTP 200. The feeds in the Success Criteria hold their expected strips, and the following Pass 1 is clean.

### U7. Documentation and solution doc

- **Goal:** The docs describe the new behavior, and the lesson is captured.
- **Requirements:** supports all.
- **Dependencies:** U6.
- **Files:**
  - Modify `docs/solutions/best-practices/catalog-sweep-and-comic-onboarding-by-source.md`: the "30-day caveat" and "Feed contents" bullets, and the Graphic Rage example.
  - Modify `CONCEPTS.md`: the "Generate phase" entry says each generator reads its latest JSON, which is untrue for the windowed sources.
  - Create a solution doc under `docs/solutions/logic-errors/` for this bug.
- **Approach:** The solution doc covers the two-part root cause, the #113 plan's wrong assumptions, and the same-date loss as recorded evidence. It links the Comics Kingdom and slug-collision docs.
- **Test expectation:** none -- documentation.
- **Verification:** The docs match the merged code, and the solution doc is on `main`.

---

## Verification Contract

| Gate | Command | Applies to |
|---|---|---|
| Strip identity | `venv/bin/python -m pytest tests/test_tinyview_strips.py -v` | U1 |
| TinyView generator | `venv/bin/python -m pytest tests/test_generate_tinyview_feeds.py -v` | U2 |
| TinyView scraper | `venv/bin/python -m pytest tests/test_tinyview_scraper.py tests/test_tinyview_scraper_local_authenticated.py -v` | U3, U4 |
| Full suite (offline, with coverage per `pytest.ini`) | `venv/bin/python -m pytest -v` | before every push |
| CI | `.github/workflows/tests.yml`, Python 3.10, 3.11 and 3.12 | U5 |
| Continuity proof | scratch regeneration compared with the committed feeds (U5 step 1) | U5 |
| Push landed | fetch, then check that HEAD is an ancestor of `origin/main` | U6, U7 |

From the worktree, run these commands with the main checkout's venv and `PYTHONPATH` set to the worktree. No test may reach a live comic source.

---

## Definition of Done

- R1-R11 are met.
- The PR is merged, the catch-up commit is on `origin/main`, and the Pass 1 after it is clean.
- The main checkout is on `main` and clean, and the worktree is removed.
- No abandoned-attempt code is left in the diff, and every new test runs offline.

| Unit | Done when |
|---|---|
| U1 | The helper exists with passing tests and no Selenium import. |
| U2 | The generator builds from the window, and its new tests pass. |
| U3 | The scraper fetches by address with own-folder images, and its tests pass, including the two updated ones. |
| U4 | Recording by address and rerun merging work, and their tests pass. |
| U5 | The continuity proof and live check pass, the operator approved the XML, and the PR is open with green CI. |
| U6 | The watched catch-up is committed after approval, and the next Pass 1 is clean. |
| U7 | The corrected docs and the new solution doc are on `main`. |
