---
title: Strip Images as media:content - Plan
type: feat
date: 2026-11-22
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Strip Images as media:content - Plan

## Goal Capsule

- **Objective:** An agent or script reading any ComicCaster feed gets each strip's image URLs from a structured element on the item, without unescaping and parsing the HTML in `<description>`. The description that feed readers render stays exactly as it is.
- **Means:** Every item carries one Media RSS `media:content` per strip image, written by `ComicFeedGenerator.create_entry` (KTD1-KTD4).
- **Authority:**
  - Requirements win on behavior, KTDs win on mechanism, and units override neither.
  - `CLAUDE.md` governs git practice. This changes feed output shape, so it ships as a branch and PR, and the operator merges.
- **Stop and ask when:**
  - A change would alter the `<description>`, `<guid>`, `<link>` or `<pubDate>` of any item.
  - Regenerated output differs from `origin/main`'s by anything other than R5 allows.
- **Execution profile:** Test-first. U1, then U2, which reuses U1's field. U3 is independent. U4 runs last on the finished branch.
- **Who finishes:** One session implements U1-U4 and opens the PR. The operator answers OQ1 and merges. The next Pass 1 regenerates the feeds.

---

## Product Contract

### Summary

Each RSS item gets one `<media:content url="..." medium="image"/>` per strip image, directly under `<item>` and in the order the description shows them. This covers all seven sources. Items without an image get none. Apart from the `xmlns:media` declaration and the new elements, regenerated feeds stay byte-identical. `public/llms.txt` tells agents the element is there.

### Problem Frame

This is step 1 of `docs/plans/2026-10-24-1300-feat-agent-access-next-steps-plan.md`. Today a strip's image exists only as an `<img>` inside escaped HTML in `<description>`, so an agent has to unescape the HTML, parse it and guess which images are the strip. Only 19 of 664 feed files carry an `<enclosure>`, and all 19 are dormant GoComics feeds last written before d1109bbad5 removed enclosures for #28.

### Requirements

**Feed content**

- R1. Every item whose strip has images carries one `media:content` per image, with the image's URL and `medium="image"`.
- R2. An item with no strip image carries no `media:content` and no empty `media:group`.
- R3. An item's `media:content` URLs are exactly the strip images its description renders, in the same order and with no extras.
- R4. R1-R3 hold for all seven sources. That includes The Far Side, whose generator writes its own description HTML.

**Compatibility**

- R5. Regenerated from the same `data/`, every feed is byte-identical to `origin/main`'s output except for `lastBuildDate`, an `xmlns:media` declaration on `<rss>` and the added `media:content` elements.

**Discoverability**

- R6. `public/llms.txt` says that feed items carry their strip images as `media:content`.

### Scope Boundaries

Considered and not built:

- **`type`, `width`, `height`, `fileSize` attributes.** Generators are network-free and don't know them; MRSS makes them optional. Would change if a consumer turns up that needs `type`.
- **HTML-unescaping URLs before writing them.** A scan of every saved scrape on 2026-11-22 found no image URL containing `&amp;` and none that isn't `http(s)` (about 300,000 URLs across all sources). Would change if a scraper starts saving escaped URLs.
- **Showing `media:content` in `scripts/preview_feeds.py`.** U4 checks R3 across every regenerated feed with a one-off script instead. Would change if drift between the two becomes a recurring review concern.
- **`ComicFeedGenerator.update_feed`.** Only the module's demo `main()` and its own tests call it, and it rebuilds items from feedparser objects. No generator uses it.
- **`media:group`, `media:title`, `media:thumbnail`, `<enclosure>`.** See KTD2 and OQ1.

### Open Questions

- OQ1. **Decide before merge: Thunderbird will show each strip twice again, the #28 symptom.** Thunderbird's feed parser reads every `media:content` into the item's enclosures, the same as `<enclosure>`. It needs no `type` and doesn't compare the URL with the `<img>` tags in the body (`parseAsRSS2` in `mailnews/extensions/newsblog/FeedParser.sys.mjs`, comm-central master on 2026-11-22). `FeedItem.sys.mjs` then writes each enclosure as an external attachment beside the HTML body. That is the path that produced #28's "hash number above where the comic is posted a 2nd time." The plan builds `media:content` because that is what step 1 asked for. The alternative is `media:thumbnail`, which Thunderbird ignores entirely and which gives agents the same URL. Switching is a change to the element name in U1's writer plus its tests. Other readers (Miniflux, SimplePie-based readers such as FreshRSS) were not checked.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Use feedgen's media extension, loaded on the feed and on each entry.** `create_feed` loads it on the `FeedGenerator`, so `<rss>` declares `xmlns:media` once. `create_entry` builds its `FeedEntry` before `add_entry` sees it, so it loads the extension on the entry too. `add_entry`'s own attempt to register it again raises `ImportError`, which feedgen catches (`feedgen/feed.py`, `add_entry`). Every feed declares the namespace, including feeds with no images, which keeps one code path and is valid XML.
- KTD2. **Each `media:content` sits directly under `<item>`, never in `media:group`.** feedgen puts content into a `media:group` named `default` unless `group` is `None` (`feedgen/ext/media.py`). MRSS reserves `media:group` for alternate versions of the same media object, and panels are separate objects.
- KTD3. **One function decides an item's strip images, with the precedence the description already uses.** A non-empty `images` list wins, skipping entries with no `url`, as `_create_multi_image_content` does. Otherwise `image_url`, then `image`. The description rendering code is not touched (R5). R3 is held by tests that compare the two.
- KTD4. **The Far Side names its strip image in a `media_urls` field.** Its generator writes the description HTML itself, `<img>` included. Passing `image_url` instead would make `create_entry` re-wrap it and drop the caption and copyright line, breaking R5. When `media_urls` is present, `create_entry` uses it for `media:content` and leaves the description alone. No other generator sets it.
- KTD5. **Attributes are `url` and `medium="image"` only.** See Scope Boundaries.

### Assumptions

- Adding elements doesn't change any `<guid>`, so no strip is re-delivered (`CONCEPTS.md`, Strip identity). Readers that already hold an item don't fetch it again, so only new items show any reader-side effect (OQ1).
- Feeds whose generator skips them when they have no new strips keep their current XML until they next publish, as with #248's language tag.

### System-Wide Impact

- **Feed readers:** see OQ1. Readers that ignore Media RSS are unaffected.
- **Agents:** `catalog.json` already points at the feeds, and `llms.txt` gains one line (R6).
- **Site preview:** `functions/fetch-feed.js` parses feeds with rss-parser and passes only `item.enclosures` through. rss-parser doesn't map `media:content` without custom fields, so the preview is unchanged.
- **Pipeline:** the first Pass 1 after merge rewrites every feed that has strips in its window, so that day's feed commit is larger than usual. Each image adds roughly 100 bytes.

### Sources and Research

- `comiccaster/feed_generator.py`: `create_feed`, `create_entry`, `_create_single_image_content`, `_create_multi_image_content`.
- `scripts/generate_farside_feeds.py`: `build_daily_entries` and `build_new_stuff_entries` build their own HTML. The other six generators pass `images` (GoComics, Comics Kingdom, Creators, TinyView) or `image_url` (New Yorker, Mr. Boffo).
- Issue #28 and d1109bbad5: why enclosures were removed.
- feedgen 1.0.0, `feedgen/ext/media.py`: `content(group=...)` and `extend_rss`.
- Thunderbird `FeedParser.sys.mjs` and `FeedItem.sys.mjs` (comm-central master, 2026-11-22): OQ1.
- PR #248's output diff: two `git archive` copies, the generators run in each from committed `data/`, `public/feeds/` diffed with `lastBuildDate` stripped.

---

## Implementation Units

### U1. Write media:content from create_entry

- **Goal:** Every generated item carries its strip images as `media:content`.
- **Requirements:** R1, R2, R3, R5.
- **Dependencies:** none.
- **Files:** `comiccaster/feed_generator.py`, `tests/test_feed_generator.py`, `tests/test_multi_image_rss.py`.
- **Approach:**
  1. Load the media extension in `create_feed` and on the entry in `create_entry` (KTD1).
  2. Add the strip-image function (KTD3), honoring `media_urls` first (KTD4).
  3. In `create_entry`, write one `media:content` per URL with `group=None` (KTD2, KTD5), after the description is built and without changing how it is built.
- **Execution note:** Write the failing tests first, against the XML that `generate_feed` writes, parsed with lxml or feedparser rather than matched as strings.
- **Patterns to follow:** The existing `test_generate_feed` and the `language` tests from #248, which assert on the written file.
- **Test scenarios:**
  - A single image given as `image` produces one `media:content` whose parent is `<item>`, with that `url` and `medium="image"`.
  - A three-image `images` list (TinyView shape) produces three elements in list order.
  - A Comics Kingdom multi-panel entry (`images` with `Panel N` alt text) produces one element per panel.
  - An `images` entry without a `url` is skipped, matching the gallery.
  - An empty `images` list with an `image_url` falls back to one element for `image_url`.
  - An entry with no image fields produces no `media:content` and no `media:group`.
  - For single-image and multi-image items, the `media:content` URLs equal the `src` of every `<img>` in the description, in order.
  - A URL containing `&` round-trips: the XML holds it escaped once, and a parser returns the original URL.
  - The written feed's `<rss>` declares `xmlns:media="http://search.yahoo.com/mrss/"`, and feedparser's `entry.media_content` lists the URLs.
  - The description HTML for an `images` entry and for an `image_url` entry is byte-identical to what the current code produces.
- **Verification:** The new tests fail on `main` and pass on the branch, and the existing feed tests pass unchanged.

### U2. Far Side entries name their strip image

- **Goal:** Far Side Daily Dose and New Stuff items carry `media:content` without any change to their description.
- **Requirements:** R4, R5.
- **Dependencies:** U1.
- **Files:** `scripts/generate_farside_feeds.py`, `tests/test_farside_generator.py`, `tests/test_feed_generator.py`.
- **Approach:** `build_daily_entries` and `build_new_stuff_entries` add `media_urls: [image_url]` to each entry (KTD4). The HTML they build stays as it is.
- **Execution note:** Test-first.
- **Test scenarios:**
  - Each Daily Dose entry carries `media_urls` equal to its comic's `image_url`, and its description is unchanged.
  - Each New Stuff entry does the same.
  - `create_entry` given `media_urls` and a pre-built HTML description writes `media:content` for those URLs and passes the description through untouched.
  - `media_urls` wins when an entry also has `images` or `image_url`.
- **Verification:** A Far Side feed generated from committed `data/` has one `media:content` per item, matching the item's `<img>`.

### U3. Tell agents about media:content

- **Goal:** An agent reading `llms.txt` learns that feed items carry their images as `media:content`.
- **Requirements:** R6.
- **Dependencies:** none.
- **Files:** `public/llms.txt`, `tests/test_agent_access.py`.
- **Approach:** One or two plain-ASCII sentences under "Feed URLs": each item's strip images are `media:content` elements (Media RSS namespace), one per image in panel order, and the description holds the same images as HTML.
- **Test scenarios:**
  - `test_llms_txt_says_where_the_catalog_and_feeds_are` also requires `media:content` in the text. The existing ASCII test still passes.
- **Verification:** The agent-access tests pass.

### U4. Prove the output diff and preview it

- **Goal:** Show that on real data the branch changes the feeds only as R5 allows and satisfies R3 everywhere.
- **Requirements:** R3, R4, R5.
- **Dependencies:** U1, U2.
- **Files:** none in the repo. Scripts and outputs live in a scratch directory.
- **Approach:**
  1. Export `origin/main` and the branch with `git archive` into two scratch copies. Run all seven generators in each against the same committed `data/`, never in the pipeline checkout.
  2. Diff the two `public/feeds/` trees with `lastBuildDate` stripped, after also removing `media:content` and the `xmlns:media` declaration from the branch side. Expect zero differences, and count the feeds and items that gained elements.
  3. On the branch side, check that every item's `media:content` URLs equal its description's `<img>` sources, and count items with none.
  4. Render a few regenerated feeds (a single-image GoComics, a multi-panel TinyView, a multi-panel Comics Kingdom, Far Side Daily Dose) with `scripts/preview_feeds.py --against origin/main`. Their items should show as unchanged.
- **Test expectation:** none. This unit verifies U1-U3 on production data.
- **Verification:** The counts and the before-and-after snippet go in the PR body.

---

## Verification Contract

| Gate | How | Applies to |
|---|---|---|
| Unit tests | `pytest -v` green locally (host venv, Python 3.14) and the PR's Tests check green on its head commit | U1, U2, U3 |
| Output diff | U4 steps 1-2: zero differences beyond R5 | U1, U2 |
| Image parity | U4 step 3: every item's `media:content` URLs equal its description's images | U1, U2 |
| Preview | U4 step 4: the previewed items read as unchanged against `origin/main` | U1, U2 |

---

## Definition of Done

- U1-U4 are done and their gates pass.
- A PR against `main` carries this plan, the code and tests, and a body with a before-and-after snippet of one item, the U4 counts and OQ1.
- No feed XML or `data/` file is in the PR. The pipeline regenerates feeds after merge.
- No scratch scripts, debug output or abandoned attempts are left in the diff.
