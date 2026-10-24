---
title: Agent access, next steps - Plan
type: feat
date: 2026-10-24
status: proposed (direction agreed; not yet planned in detail; run ce-plan before implementing)
---

# Agent access, next steps - Plan

## Goal

AI agents can find any comic ComicCaster offers, get its feed URL, read its latest
strip and hand a person a ready-made subscription, without scraping `index.html`
and without ComicCaster running more code that the internet can reach than it has to.

## Where it stands (2026-10-24)

Done, all merged:

- **#246:** `public/catalog.json` is one list of every comic with one schema
  (`slug`, `name`, `author`, `source`, `category`, `language`, `feed_url`,
  `site_url`, `has_feed`, `last_updated`), rebuilt by Pass 1, Pass 2 and push
  recovery. `public/llms.txt` explains it, `robots.txt` welcomes crawlers, and
  feeds, `/rss/*` and the catalog send `Access-Control-Allow-Origin: *`.
- **#244:** the feed-preview function no longer fetches arbitrary URLs. This
  mattered for agent access too: an agent-facing site shouldn't double as an
  open proxy.
- **#248:** Spanish feeds declare `<language>es</language>`, matching the
  catalog's `language`.

## Guiding constraint

The operator's other concern on 2026-10-24 was security. Each new endpoint is
more code the internet can reach, so prefer static files, which every agent can
fetch and which run no code. Add server-side code only where a static file can't
do the job, and then keep it read-only, with no outbound fetching.

## Next steps, in order

1. **Strip images as structured data.** Today each item's image is inside escaped
   HTML in `<description>`. Only 19 of 664 feeds carry an `<enclosure>` or
   `media:content` (counted 2026-10-24). Emit `media:content` (or an enclosure)
   per image in `comiccaster/feed_generator.py`, so agents and readers get the
   strip without parsing HTML. Generator change, network-free, test-first.
   Check: regenerated feeds differ only by the added elements, the same
   before-and-after diff #248 used.
2. **An OPML link that works with GET.** `functions/generate-opml.js` only accepts
   a POSTed JSON body, so an agent can't give a person a link. Options: a GET
   variant (`?type=daily&comics=a,b`) on the existing function, or have agents
   build OPML themselves from `catalog.json` (already described in `llms.txt`).
   Decide whether the GET variant is worth a code change at all.
3. **A read-only MCP server, last.** Tools such as `search_comics`,
   `get_comic`, `latest_strip` and `build_opml`, reading only `catalog.json`
   and the feeds, with no outbound fetches, so it can never become another
   open proxy. Steps 1 and 2 make it a thin wrapper. Without them it would
   re-implement the catalog. Hosting options are a Netlify function next to the
   others, or a separate Worker. Decide when it's picked up.

## Related findings, not agent work

- Awkward Zombie and Wilde Life external feeds return HTTP 500 (Open Decisions in
  `docs/STATUS.md`). The catalog still lists them.
- Previewing Dumbing of Age fails from Netlify's servers (Known Issues in
  `docs/STATUS.md`).

## Out of scope

- Self-hosting strip images (see the read-later WONTFIX, #91).
- Any write or authenticated endpoint.
