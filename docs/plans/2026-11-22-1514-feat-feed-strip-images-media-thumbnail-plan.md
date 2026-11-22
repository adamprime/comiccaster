---
title: Strip Images as media:thumbnail - Plan
type: feat
date: 2026-11-22
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Strip Images as media:thumbnail - Plan

## Goal Capsule

- **Objective:** An agent or script reading any ComicCaster feed the pipeline rebuilds from now on gets each strip's image URLs from a structured element on the item, without unescaping and parsing the HTML in `<description>`. What feed readers show stays exactly as it is, including Thunderbird, where #28's doubled strip must not come back.
- **Means:** Every item carries one Media RSS `media:thumbnail` per strip image, written by `ComicFeedGenerator.create_entry` (KD1, KTD1-KTD5).
- **Authority:**
  - Requirements win on behavior, KTDs win on mechanism, and units override neither.
  - `CLAUDE.md` governs git practice. This changes feed output shape, so it ships as a branch and PR, and the operator merges after rechecking the regenerated feeds in Thunderbird.
- **Stop and ask when:**
  - A change would alter the `<description>`, `<guid>`, `<link>` or `<pubDate>` of any item.
  - Regenerated output differs from `origin/main`'s by anything other than R5 allows, or any feed's item count changes.
- **Execution profile:** Test-first. U1, then U2, which reuses U1's field. U3 is independent. U4 runs last on the finished branch.
- **Who finishes:** One session implements U1-U4 and opens the PR. The operator rechecks in Thunderbird and merges. The next Pass 1 regenerates the feeds.

---

## Product Contract

### Summary

Each RSS item gets one `<media:thumbnail url="..."/>` per strip image, directly under `<item>` and in the order the description shows them. This covers all seven sources. Items without an image get none, and no item carries `media:content` or `<enclosure>`. Apart from the `xmlns:media` declaration and the new elements, regenerated feeds stay byte-identical. `public/llms.txt` tells agents the element is there and that its URL is the full-size strip.

### Problem Frame

This is step 1 of `docs/plans/2026-10-24-1300-feat-agent-access-next-steps-plan.md`. Today a strip's image exists only as an `<img>` inside escaped HTML in `<description>`, so an agent has to unescape the HTML, parse it and guess which images are the strip.

The obvious structured elements, `<enclosure>` and `media:content`, both double the strip in Thunderbird. Thunderbird shows each one as an attachment below the description. That was #28, which d1109bbad5 fixed by removing enclosures, so only 19 of 664 feed files still carry an `<enclosure>`. All 19 are dormant GoComics feeds last written before that fix.

### Key Decisions

- KD1. **`media:thumbnail`, not `media:content` or `<enclosure>`.** (session-settled: user-approved — chosen over media:content: Thunderbird 160 doubled every strip with media:content and showed each strip once with media:thumbnail.) Governs R1, R3, R6, R7.

### Requirements

**Feed content**

- R1. Every item whose strip has images carries one `media:thumbnail` per image, whose `url` is the image's URL.
- R2. An item with no strip image carries no `media:thumbnail` and no empty `media:group`.
- R3. An item's `media:thumbnail` URLs are exactly the strip images its description renders, in the same order and with no extras.
- R4. R1-R3 hold for all seven sources. That includes The Far Side, whose generator writes its own description HTML.
- R7. No generated item carries `media:content` or `<enclosure>`.

**Compatibility**

- R5. Regenerated from the same `data/`, every feed has the same items as `origin/main`'s output and is byte-identical to it, except for `lastBuildDate`, an `xmlns:media` declaration on `<rss>` and the added `media:thumbnail` elements.

**Discoverability**

- R6. `public/llms.txt` says that feed items carry their strip images as `media:thumbnail`, and that each `url` is the full-size strip despite the element's name.

### Scope Boundaries

Considered and not built:

- **`width` and `height` attributes.** Generators are network-free and don't know them, and Media RSS makes them optional. Would change if a consumer turns up that needs them.
- **HTML-unescaping URLs before writing them.** A scan of every saved scrape on 2026-11-22 found no image URL containing `&amp;` and none that isn't `http(s)` (about 300,000 URLs across all sources). Would change if a scraper starts saving escaped URLs.
- **Showing thumbnails in `scripts/preview_feeds.py`.** U4 checks R3 across every regenerated feed with a one-off script instead. Would change if drift between the two becomes a recurring review concern.
- **`ComicFeedGenerator.update_feed`.** Only the module's demo `main()` and its own tests call it, and it rebuilds items from feedparser objects. No generator uses it.
- **Removing the 19 dormant feeds' old `<enclosure>` elements.** Their generators skip them, and rewriting them would touch feed XML this PR leaves alone.
- **`media:content`, `<enclosure>`, `media:group`, `media:title`.** See KD1 and KTD2.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Use feedgen's media extension, loaded on the feed and on each entry.** `create_feed` loads it on the `FeedGenerator`, so `<rss>` declares `xmlns:media` once. `create_entry` builds its `FeedEntry` before `add_entry` sees it, so it loads the extension on the entry too. `add_entry`'s own attempt to register it again raises `ImportError`, which feedgen catches (`feedgen/feed.py`, `add_entry`). Every feed declares the namespace, including feeds with no images, which keeps one code path and is valid XML.
- KTD2. **Each `media:thumbnail` sits directly under `<item>`, never in `media:group`.** feedgen puts thumbnails into a `media:group` named `default` unless `group` is `None` (`feedgen/ext/media.py`). Media RSS reserves `media:group` for alternate versions of the same media object, and panels are separate images.
- KTD3. **One function decides an item's strip images, with the precedence the description already uses.** A non-empty `images` list wins, skipping entries with no `url`, as `_create_multi_image_content` does. Otherwise `image_url`, then `image`. The description rendering code is not touched (R5). R3 is held by tests that compare the two.
- KTD4. **The Far Side names its strip image in a `media_urls` field.** Its generator writes the description HTML itself, `<img>` included. Passing `image_url` instead would make `create_entry` re-wrap it and drop the caption and copyright line, breaking R5. When `media_urls` is present, `create_entry` uses it for the thumbnails. Far Side entries carry no `images` or `image_url`, so their description passes through unchanged. No other generator sets it.
- KTD5. **The only attribute is `url`.** `media:thumbnail` has no `medium` attribute, and feedgen's `thumbnail()` raises `ValueError` for one. `generate_feed` catches exceptions per entry and moves on, so a bad attribute would silently drop every item with an image. U4's per-feed item count guards against that.

### Assumptions

- Adding elements doesn't change any `<guid>`, so no strip is re-delivered (`CONCEPTS.md`, Strip identity).
- A generator skips a feed with no strips in its window, so that feed keeps its current XML until it next publishes, as with #248's language tag. Regenerating from the committed data on 2026-11-22 rewrote 520 of 664 feed files. The other 144 are dormant, holding 1,230 items with an `<img>` in the description and no thumbnail. Many will never be rebuilt, because their comics stopped publishing upstream, so `llms.txt` says so (U3).

### System-Wide Impact

- **Feed readers:** Thunderbird shows the strip once, unchanged (KD1). Readers that use `media:thumbnail` for list-view previews, such as Feedly and Inoreader, may start showing the strip there. SimplePie builds a link-less fallback enclosure from a thumbnail. FreshRSS, which is SimplePie-based, stores only enclosures that have a link, and hides a thumbnail whose URL is already in the content.
- **Agents:** `catalog.json` already points at the feeds, and `llms.txt` gains one paragraph (R6).
- **Site preview:** `functions/fetch-feed.js` parses feeds with rss-parser and passes only `item.enclosures` through. rss-parser doesn't map Media RSS without custom fields, so the preview is unchanged.
- **Pipeline:** the first Pass 1 after merge rewrites every feed that has strips in its window, so that day's feed commit is larger than usual. Each image adds roughly 100 bytes.

### Sources and Research

- **Thunderbird 160, tested on the pipeline host on 2026-11-22 and checked by eye by the operator**, with the feed account set to "Show the summary":
  - The live `main` feed: each strip once, no attachments.
  - Popeye generated with `media:content`: the strip, then a divider naming the image file and the whole strip again, plus a "2 attachments, size unknown" bar and a paperclip on every item.
  - The same file with each `media:content` rewritten to `media:thumbnail`: identical to `main`.
- Thunderbird source (comm-central master, 2026-11-22): `parseAsRSS2` in `mailnews/extensions/newsblog/FeedParser.sys.mjs` reads every `media:content` into the item's enclosures and never reads `media:thumbnail`. `FeedItem.sys.mjs` writes each enclosure as an attachment beside the HTML body.
- Issue #28 and d1109bbad5: the original doubled strip, reported from Feed-on-Feeds and Thunderbird. Feed-on-Feeds parses with SimplePie, whose `Item::get_enclosures()` also turns `media:content` into an enclosure.
- `comiccaster/feed_generator.py`: `create_feed`, `create_entry`, `_create_single_image_content`, `_create_multi_image_content`.
- `scripts/generate_farside_feeds.py`: `build_daily_entries` and `build_new_stuff_entries` build their own HTML. The other six generators pass `images` (GoComics, Comics Kingdom, Creators, TinyView) or `image_url` (New Yorker, Mr. Boffo).
- feedgen 1.0.0, `feedgen/ext/media.py`: `thumbnail(group=...)` accepts `url`, `height`, `width`, `time`.
- PR #248's output diff: two `git archive` copies, the generators run in each from committed `data/`, `public/feeds/` diffed with `lastBuildDate` stripped.

---

## Implementation Units

### U1. Write media:thumbnail from create_entry

- **Goal:** Every generated item carries its strip images as `media:thumbnail`, and none carries `media:content` or `<enclosure>`.
- **Requirements:** R1, R2, R3, R5, R7.
- **Dependencies:** none.
- **Files:** `comiccaster/feed_generator.py`, `tests/test_feed_generator.py`, `tests/test_multi_image_rss.py`.
- **Approach:**
  1. Load the media extension in `create_feed` and on the entry in `create_entry` (KTD1).
  2. Add the strip-image function (KTD3), honoring `media_urls` first (KTD4).
  3. In `create_entry`, write one `media:thumbnail` per URL with `group=None` (KTD2, KTD5), after the description is built and without changing how it is built.
- **Execution note:** Write the failing tests first, against the XML that `generate_feed` writes, parsed with lxml or feedparser rather than matched as strings.
- **Patterns to follow:** The existing `test_generate_feed` and the `language` tests from #248, which assert on the written file.
- **Test scenarios:**
  - A single image given as `image` produces one `media:thumbnail` whose parent is `<item>` and whose only attribute is `url`.
  - A three-image `images` list (TinyView shape) produces three elements in list order.
  - A Comics Kingdom multi-panel entry (`images` with `Panel N` alt text) produces one element per panel.
  - An `images` entry without a `url` is skipped, matching the gallery.
  - An empty `images` list with an `image_url` falls back to one element for `image_url`.
  - An entry with no image fields produces no Media RSS elements at all.
  - For single-image and multi-image items, the thumbnail URLs equal the `src` of every `<img>` in the description, in order.
  - #28 regression: a feed mixing `image`, `image_url`, `images`, `media_urls` and imageless entries keeps all its items, contains no `media:content` and no `<enclosure>`, and each item's thumbnails equal its description images.
  - A URL containing `&` round-trips: the XML holds it escaped once, and a parser returns the original URL.
  - The written feed's `<rss>` declares `xmlns:media="http://search.yahoo.com/mrss/"`, and feedparser's `entry.media_thumbnail` lists the URLs.
  - The description HTML for an `images` entry and for an `image_url` entry is byte-identical to what the code produced before this change.
- **Verification:** The new tests fail on `main` and pass on the branch, and the existing feed tests pass unchanged.

### U2. Far Side entries name their strip image

- **Goal:** Far Side Daily Dose and New Stuff items carry `media:thumbnail` without any change to their description.
- **Requirements:** R4, R5.
- **Dependencies:** U1.
- **Files:** `scripts/generate_farside_feeds.py`, `tests/test_farside_generator.py`, `tests/test_feed_generator.py`.
- **Approach:** `build_daily_entries` and `build_new_stuff_entries` add `media_urls: [image_url]` to each entry (KTD4). The HTML they build stays as it is.
- **Execution note:** Test-first.
- **Test scenarios:**
  - Each Daily Dose entry carries `media_urls` equal to its comic's `image_url`, and its description still shows exactly that image.
  - Each New Stuff entry does the same.
  - `create_entry` given `media_urls` and a pre-built HTML description writes thumbnails for those URLs and passes the description through untouched.
- **Verification:** A Far Side feed generated from committed `data/` has one `media:thumbnail` per item, matching the item's `<img>`.

### U3. Tell agents about media:thumbnail

- **Goal:** An agent reading `llms.txt` learns where the images are and what the element's URL holds.
- **Requirements:** R6.
- **Dependencies:** none.
- **Files:** `public/llms.txt`, `tests/test_agent_access.py`.
- **Approach:** A short plain-ASCII paragraph under "Feed URLs". It says each item's strip images are `media:thumbnail` elements (Media RSS namespace), one per image in panel order, that each `url` is the full-size strip the description also shows, and that feeds not rebuilt since this change, mostly comics that stopped publishing, have their images only in the description.
- **Test scenarios:**
  - `test_llms_txt_says_where_the_catalog_and_feeds_are` also requires `media:thumbnail` in the text. The existing ASCII test still passes.
- **Verification:** The agent-access tests pass.

### U4. Prove the output diff and preview it

- **Goal:** Show that on real data the branch keeps every item, changes the feeds only as R5 allows, and satisfies R3 and R7 everywhere.
- **Requirements:** R3, R4, R5, R7.
- **Dependencies:** U1, U2.
- **Files:** none in the repo. Scripts and outputs live in a scratch directory.
- **Approach:**
  1. Export `origin/main` with `git archive` into two scratch copies and copy the branch's changed source files into one. Run all seven generators in each against the same committed `data/`, never in the pipeline checkout.
  2. Compare each feed's item count between the two copies.
  3. Diff the two `public/feeds/` trees with `lastBuildDate` stripped, after also removing `media:thumbnail` and the `xmlns:media` declaration from the branch side. Expect zero differences, and count the feeds and items that gained elements.
  4. In every feed the run rewrote (one that differs from the committed copy), check that no item carries `media:content` or `<enclosure>`, that each item's thumbnail URLs equal its description's `<img>` sources, and count items with none. Count the untouched feeds separately (see Assumptions).
  5. Render a few regenerated feeds (a single-image GoComics, a multi-panel TinyView, a multi-panel Comics Kingdom, Far Side Daily Dose, New Yorker) with `scripts/preview_feeds.py --against origin/main`. Their items should show as unchanged.
- **Test expectation:** none. This unit verifies U1-U3 on production data.
- **Verification:** The counts and the before-and-after snippet go in the PR body.

---

## Verification Contract

| Gate | How | Applies to |
|---|---|---|
| Unit tests | `pytest -v` green locally (host venv, Python 3.14) and the PR's Tests check green on its head commit | U1, U2, U3 |
| Item counts | U4 step 2: every feed has the same number of items on both sides | U1, U2 |
| Output diff | U4 step 3: zero differences beyond R5 | U1, U2 |
| Image parity | U4 step 4: in every rewritten feed, no `media:content` or `<enclosure>`, and each item's thumbnails equal its description's images | U1, U2 |
| Preview | U4 step 5: the previewed items read as unchanged against `origin/main` | U1, U2 |
| Thunderbird | The operator opens feeds regenerated from the PR's head commit in Thunderbird and sees each strip once, with no attachments | U1 |

---

## Definition of Done

- U1-U4 are done and their gates pass, the Thunderbird recheck included.
- A PR against `main` carries this plan, the code and tests, and a body with a before-and-after snippet of one item, the U4 counts and the Thunderbird evidence.
- No feed XML or `data/` file is in the PR. The pipeline regenerates feeds after merge.
- No scratch scripts, debug output or abandoned attempts are left in the diff.
