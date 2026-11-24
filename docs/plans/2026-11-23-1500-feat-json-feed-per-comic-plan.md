---
title: JSON Feed per Comic - Plan (not started)
type: feat
date: 2026-11-23
status: proposed
---

# JSON Feed per Comic - Plan (not started)

A forward-looking note, written while fixing issue #269. Nothing here is built.
Deepen it with `ce-plan` before starting.

## Why

Agents want each strip's image URLs as data. RSS has no element for that which
every reader leaves alone: `<enclosure>`, `media:content` and `media:thumbnail`
each doubled the strip in some reader (#28, #267, #269; see
`docs/solutions/ui-bugs/media-thumbnail-doubles-strips-in-rss-guard.md`). The
fix for #269 was `comiccaster:images`, an element in our own namespace. It
works, but it is non-standard: an agent has to read `llms.txt` to know it
exists.

JSON Feed 1.1 (https://jsonfeed.org/version/1.1) is a standard built for this.
An item has `image` (the main image), `content_html`, and `attachments`. A
JSON file sits beside the RSS, so no feed reader subscribed to the RSS ever
sees it.

## Shape

- `public/feeds/<slug>.json` beside each `public/feeds/<slug>.xml`, written by
  the same Phase 2 generator call from the same entries, so the two can't drift.
- Per item: `id` (the RSS guid), `url`, `title`, `date_published`,
  `content_html` (the same description HTML), `image` (the first strip image).
- `catalog.json` gains a `json_feed_url` per comic; `llms.txt` points agents at
  it first.
- `public/_headers` gives `/feeds/*.json` the same CORS header as the XML.

## Open questions

1. **Multi-panel strips.** `image` holds one URL. The options are
   `attachments` (one per panel, `mime_type` image/*) or a `_comiccaster`
   extension object with an `images` array (JSON Feed reserves `_`-prefixed
   keys for extensions). Check how JSON Feed readers show image attachments
   before choosing: the doubling problem could come back for anyone who
   subscribes to the JSON in a reader.
2. **Does `comiccaster:images` stay?** Keeping it costs nothing and breaks no
   one. Removing it changes feed shape again. Default: keep.
3. **Repo size and deploy time.** About 664 more generated files committed
   daily. Measure the commit and Netlify deploy cost first.
4. **Where it sits in the agent-access plan.** It is not one of the steps in
   `docs/plans/2026-10-24-1300-feat-agent-access-next-steps-plan.md`. Step 3
   (the MCP server) could read JSON feeds instead of parsing XML, which argues
   for doing this first.

## Not in scope

Changing the RSS feeds, an Atom variant, or serving JSON from a function.
