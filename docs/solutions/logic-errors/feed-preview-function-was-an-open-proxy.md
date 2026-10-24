---
title: The feed-preview function fetched any URL — harden every caller-supplied fetch, not just the one in front of you
date: 2026-10-24
category: logic-errors
module: netlify-functions
problem_type: security
component: functions/fetch-feed.js
severity: medium
applies_when:
  - "Writing or reviewing any Netlify function that fetches a URL taken from the request"
  - "Hardening one function against SSRF: check its siblings in functions/ too"
  - "Changing what the preview page can preview (deploy previews, external feeds)"
  - "An external feed's preview fails with 'Failed to fetch or parse feed' but the feed works in a reader"
tags: [ssrf, open-proxy, netlify-functions, allowlist, redirects, external-rss, deploy-preview]
stack: [javascript, netlify]
---

## TL;DR

`functions/fetch-feed.js`, which backs `public/preview.html`, passed whatever
URL it was POSTed straight to `rss-parser`. On 2026-10-24 POSTing Hacker News'
RSS URL to the live site returned Hacker News' feed: an open, unauthenticated
proxy running on the Netlify account. The image proxy had been hardened against
this in June (see `best-practices/mixed-content-and-single-image-comic-sources.md`
§3); the sibling function that does the same thing for feeds never was. When you
harden one function that fetches a caller-supplied URL, grep `functions/` for
the others.

## The allowlist had to be wider than "comiccaster.xyz only"

The preview page previews three kinds of URL, and a strict own-domain check
breaks two of them:

1. **Our feeds on production** — `https://comiccaster.xyz/feeds/<slug>.xml`.
2. **Our feeds on a deploy preview** — `public/index.html` builds the preview
   link from `window.location.origin`, so a deploy preview previews its own
   branch's feed at `https://deploy-preview-N--comiccaster.netlify.app/feeds/<slug>.xml`.
   The Netlify site name is `comiccaster`, so `<deploy>--comiccaster.netlify.app`
   covers deploy previews and branch deploys.
3. **External RSS comics** — previewed at their own `feed_url` from
   `public/external_comics_list.json`.

The fix allows exactly those: `https` on our hosts (plus `http://localhost` when
`CONTEXT=dev`), path matching `^/feeds/[A-Za-z0-9_-]+\.xml$` with no query, no
port, no credentials; or a URL that equals a listed `feed_url` character for
character. Everything else gets a 403 before any request is made.

## Redirects: don't follow them, fix the catalog instead

`rss-parser`'s `parseURL` follows redirects, so a listed feed that redirected
could send the function anywhere, allowlist or not. The function now fetches
with `redirect: 'manual'` and hands the body to `parser.parseString`.

That broke one external comic: `https://www.buttersafe.com/feed/` 302s to
`http://feeds.feedburner.com/buttersafe`. The fix was to list the real feed,
`https://feeds.feedburner.com/buttersafe`, not to follow the redirect. If an
external comic's preview starts failing while the feed still works in a reader,
check for a new redirect (`curl -sI <feed_url>`) and update its `feed_url`.

## How it's tested

`tests/test_fetch_feed_function.py` runs the real handler under `node` with
`fetch` and `rss-parser` stubbed, so it stays offline. It checks our feeds and
every listed external feed are allowed, a list of lookalike and internal URLs
are refused without a fetch, and a redirect is not followed. The tests skip
when `node` is missing; GitHub's Ubuntu runners have it.
