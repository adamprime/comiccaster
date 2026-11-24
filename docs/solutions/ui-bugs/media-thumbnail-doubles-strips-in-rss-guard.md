---
title: media:thumbnail shows every strip twice in RSS Guard; name strip images in our own namespace
date: 2026-11-23
category: ui-bugs
module: feed-generation
problem_type: regression
component: comiccaster/feed_generator.py
severity: medium
applies_when:
  - "Adding any per-item element to the generated feed XML (images, media, enclosures)"
  - "A reader reports seeing each comic strip twice"
  - "Choosing how to expose strip images to agents or tools without breaking feed readers"
tags: [rss, media-rss, media-thumbnail, enclosure, rss-guard, feed-readers, agent-access, namespace, feedparser, regression, issue-269]
stack: [python, feedgen]
github_issues: [269]
---

## TL;DR

#267 named each strip image in `<media:thumbnail>` after a Thunderbird test
showed that element was safe there. The first live run with it (2026-11-23)
doubled every strip in RSS Guard (issue #269). No standard element is safe:
some reader draws each of them as a second copy of the image that is already in
the description.

Feeds now carry one `<comiccaster:images>` per item, in ComicCaster's own
namespace (`https://comiccaster.xyz/ns/feed`). Its text is the strip's image
URLs in panel order, separated by a space. Readers skip an element in a
namespace they don't know.

## Why RSS Guard doubled it

From RSS Guard's source:

- `src/librssguard-standard/src/parsers/feedparser.cpp`, `xmlMrssGetEnclosures`:
  every `media:content` and every `media:thumbnail` becomes an article
  attachment with a default image MIME type.
- `src/librssguard/miscellaneous/skinfactory.cpp`: with "Display attachments
  directly in article" on, every image attachment is drawn above the body.

The reporter's screenshot shows exactly that: an `(IMAGE/JPG)` attachment chip,
the strip, then the description with the strip again. Articles fetched before
the change kept their old copies and looked fine.

## Reproduced in RSS Guard 5.3.0

On a Linux box, RSS Guard 5.3.0 (the official AppImage, `text-qt6`) fetched two
trimmed Garfield feeds, three items each, and this is what it stored per
article in the `enclosures` column of its `Messages` table:

| Feed | Stored attachments |
|---|---|
| BEFORE: `main`, with `media:thumbnail` | one `image/jpg` attachment per article, the strip's URL |
| AFTER: PR #270, with `comiccaster:images` | `[]` for every article |

The stored article body was the same length in both. Nobody looked at the
window: the box's screen wasn't reachable, so RSS Guard was driven over ssh
through its accessibility interface (AT-SPI, `python3-gi`; launch it with
`QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1` and `WAYLAND_DISPLAY`,
`XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` pointing at the logged-in
session, and `-d <folder>` for a throwaway profile). The doubled image itself
is the reporter's screenshot plus the skin code above, which draws every image
attachment.

Not explained: the reporter said non-GoComics feeds were fine, though The Far
Side carried the same element.

## What other readers do

Dedup is each reader's choice. NewsBlur skips an enclosure image whose URL is
already in the story body. Thunderbird ignores `media:thumbnail` but draws
`media:content` and `<enclosure>`. RSS Guard draws all of them. The advice that
recurs in WordPress and Hugo forums is to put an image in one place only: the
body or a media element, never both.

| Way to name the image | Known to double in |
|---|---|
| `<enclosure>` | Thunderbird, Feed-on-Feeds (#28) |
| `media:content` | Thunderbird (#267, first version), RSS Guard |
| `media:thumbnail` | RSS Guard (#269) |
| element in our own namespace | none known |

## Why one element, not one per image

`feedparser` exposes an element it doesn't know as `entry.<prefix>_<name>` and
keeps only the last one when it repeats. One `<comiccaster:image>` per panel
would have given a feedparser user only the last panel. With a single element,
`entry.comiccaster_images.split()` is the whole list. A URL can't contain
whitespace, and the generator percent-encodes any that does.

## Guard

`tests/test_feed_generator.py`:
`test_no_item_carries_a_media_rss_element_or_an_enclosure` fails if any
generated feed contains `media:` or the Media RSS namespace at all.
`test_the_feed_declares_the_comiccaster_namespace_and_feedparser_reads_every_image`
pins the feedparser behavior.

## Lesson

One reader is not a reader test. Before a feed-shape change merges, look at it
in Thunderbird (procedure in `media-content-doubles-strips-in-thunderbird.md`)
and in RSS Guard, which is the strictest one found so far because it draws
every Media RSS element.

## Related

- `media-content-doubles-strips-in-thunderbird.md`: the first round, and how to
  test in a real reader
- `docs/plans/2026-11-23-1500-feat-json-feed-per-comic-plan.md`: the
  standards-based way to give agents images, not started
- `CONCEPTS.md`, "Strip images"
