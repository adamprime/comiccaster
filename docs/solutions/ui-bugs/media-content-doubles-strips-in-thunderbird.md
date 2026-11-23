---
title: media:content (like enclosures) shows every strip twice in Thunderbird; name strip images with media:thumbnail
date: 2026-11-22
category: ui-bugs
module: feed-generation
problem_type: regression
component: comiccaster/feed_generator.py
severity: medium
applies_when:
  - "Adding any per-item element to the generated feed XML (images, media, enclosures)"
  - "A reader reports seeing each comic strip twice"
  - "Choosing how to expose strip images to agents or tools without breaking feed readers"
tags: [rss, media-rss, media-content, media-thumbnail, enclosure, thunderbird, feed-readers, agent-access, regression, issue-28]
stack: [python, feedgen]
github_prs: [267]
---

> **Superseded in part (2026-11-23):** `media:thumbnail` is safe in Thunderbird
> but doubles every strip in RSS Guard (issue #269). Feeds now use
> `comiccaster:images` instead. See
> `media-thumbnail-doubles-strips-in-rss-guard.md`. The Thunderbird test
> procedure below still applies.

## TL;DR

Agent access step 1 (#267) wanted each feed item to name its strip images as
structured data, so agents wouldn't have to parse the description HTML. The
first version emitted one `<media:content url="..." medium="image"/>` per image.
Every test passed. In Thunderbird it showed every strip twice. The description
rendered the strip, then Thunderbird drew each `media:content` as an inline
image attachment below it, with a paperclip on the item and an "N attachments"
bar. That is issue #28 again. #28 came from `<enclosure>` and was fixed in
d1109bbad5 by dropping enclosures.

`<media:thumbnail url="..."/>` carries the same URLs, and Thunderbird ignores it.
The strip shows once, the same as before the change. #267 shipped that way
(merged as b57b055ab2).

## How it was settled

The PR session predicted the doubling from Thunderbird's source (`parseAsRSS2`
in `mailnews/extensions/newsblog/FeedParser.sys.mjs` turns media content into
enclosures) but couldn't run Thunderbird. The operator checked by eye in
Thunderbird 160, with the feed account set to "Show the summary". (Otherwise
Thunderbird loads the comic's web page and never shows the feed content.)

| Test feed | What Thunderbird showed |
|---|---|
| BEFORE: the live `main` feed | the strip once, no attachments |
| AFTER: generated with `media:content` | the strip, a divider naming the `.jpg`, the strip again; paperclip, "2 attachments" bar |
| THUMB: the AFTER file with only `media:content` changed to `media:thumbnail` | the strip once, no paperclip or bar |
| NEW: generated from the reworked PR | the strip once |

Other readers vary. FreshRSS hides the duplicate. Feed-on-Feeds, where #28 was
first reported, puts the image in a separate reveal. Feedly, Inoreader,
NetNewsWire and Miniflux weren't checked. `media:thumbnail` is safe in all of
the ones that were.

## Why the tests didn't catch it

The tests check the XML we write. They can't show how a reader displays it.
`scripts/preview_feeds.py` renders descriptions and doesn't read media
elements, so its output was identical before and after. A feed-shape change
needs one look in a real reader before it merges. CLAUDE.md and AGENTS.md now
say so.

## How to test a feed change in a real reader

Do it from scratch space, never from the pipeline checkout:

1. Generate the changed feeds from the PR's commit in a detached worktree, with
   the host venv's Python and `PYTHONPATH` set to the worktree.
2. Make trimmed test copies, with three items each, of the live `main` feed and
   the new one. Prefix each channel title (`BEFORE`, `AFTER`) and append a tag to
   each `<guid>` (`#before`, `#after`). Otherwise the reader treats identical
   items as already seen.
3. Serve them locally: `python3 -m http.server 8765 --bind 127.0.0.1 --directory <dir>`.
4. Thunderbird is installed at `~/Applications/Thunderbird.app`. The cask needs
   `brew install --cask --appdir="$HOME/Applications" thunderbird`, because
   `/Applications` wants sudo. Create a Feed Account, set it to "Show the
   summary", subscribe to the local URLs, and compare the same item in each.
   Computer use couldn't see this Thunderbird, so the operator checks it over
   Screen Sharing.
5. Afterwards, stop the server and remove the worktree.

## Guard

`tests/test_feed_generator.py` asserts that no generated item carries
`media:content` or `<enclosure>` (`test_no_item_carries_media_content_or_an_enclosure`).
It also asserts that each item's thumbnails name exactly the images its
description shows, in order. `generate_feed` swallows per-entry exceptions, so
a broken image element would silently drop items. The PR's all-sources
regeneration therefore also compared item counts per feed, and none lost an
item.

## Related

- `docs/plans/2026-11-22-1514-feat-feed-strip-images-media-thumbnail-plan.md`:
  the plan, with KD1 and the full evidence
- `CONCEPTS.md`, "Strip images"
- Issue #28 and d1109bbad5: the original doubled strip
