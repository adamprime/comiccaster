---
title: Agent access, next steps - Plan
type: feat
date: 2026-10-24
status: in progress (step 1 done in #267; step 2 decided 2026-11-22, see its note; run ce-plan on step 3 before implementing it)
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
   Planned in detail on 2026-11-22:
   `docs/plans/2026-11-22-1514-feat-feed-strip-images-media-thumbnail-plan.md`.
   It emits `media:thumbnail`, not `media:content`: a Thunderbird test showed
   `media:content` doubling every strip, the #28 regression.
2. **An OPML link that works with GET.** `functions/generate-opml.js` only accepts
   a POSTed JSON body, so an agent can't give a person a link. Options: a GET
   variant (`?type=daily&comics=a,b`) on the existing function, or have agents
   build OPML themselves from `catalog.json` (already described in `llms.txt`).
   Decide whether the GET variant is worth a code change at all.

   **Decided 2026-11-22: yes, add the GET form.** An agent can't hand a person a
   file it wrote; it can hand them a link, and a person can share a link. The
   change runs no new kind of code: same function, same lists, still no outbound
   fetch, just a second way to send the same input. Writing OPML from
   `catalog.json` stays documented for agents that need to mix categories.
   The design:

   - `GET /.netlify/functions/generate-opml?type=daily&comics=peanuts,pickles`
     returns the POST form's OPML with `Content-Disposition: attachment`, so a
     browser downloads it. POST stays as it is for `public/index.html`.
   - **One category per link.** Slugs aren't unique across the lists:
     `false-knees` is a ComicCaster feed under daily and the publisher's own
     feed under external, and 60-odd Spanish and political slugs are in the
     daily list too. The category is what decides which feed a slug means. A
     mixed link would need its own per-slug syntax for a case no caller has
     yet, and the OPML has one category outline and one filename.
   - **A link keeps only slugs in its own category's list.** The POST form's
     filter (`comicFeedExists`) also passes a slug from another category, or
     any path that names a feed file such as `../feeds/pickles`, which then gets
     a made-up name or a URL that 404s. A link narrows that filter to the
     requested category, so nothing from the query reaches the OPML except a
     listed slug.
   - **Caps:** at most 100 slugs and a 5,000-character query. 100 of the
     longest real slugs, commas percent-encoded, fit inside the length cap.
   - `type` must be daily, political, spanish, tinyview or external (default
     daily); the Far Side and New Yorker comics are in the daily list.
   - GET responses send `Access-Control-Allow-Origin: *`, like the feeds and
     the catalog, so a browser-based agent can read them.
   - Found on the way, fixed for both forms: comic names weren't XML-escaped,
     so a bundle with Barney & Clyde (or any of the seven `&` names) was not
     well-formed and a strict reader would reject the whole file.
3. **A read-only MCP server, last.** Tools such as `search_comics`,
   `get_comic`, `latest_strip` and `build_opml`, reading only `catalog.json`
   and the feeds, with no outbound fetches, so it can never become another
   open proxy. Steps 1 and 2 make it a thin wrapper. Without them it would
   re-implement the catalog. Hosting options are a Netlify function next to the
   others, or a separate Worker. Decide when it's picked up.

## Related findings, not agent work

- Awkward Zombie and Wilde Life external feeds returned HTTP 500. They recovered
  by 2026-11-03 and stay listed.
- Previewing Dumbing of Age failed on 2026-10-24. It no longer reproduces as of
  2026-11-22, and the preview function now says why a preview fails
  (2387d61481).

## Out of scope

- Self-hosting strip images (see the read-later WONTFIX, #91).
- Any write or authenticated endpoint.
