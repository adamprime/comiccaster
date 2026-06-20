---
title: Adding a self-hosted comic source — image hosting, feed shape, and proxy safety
date: 2026-06-20
category: best-practices
module: comic-sources
problem_type: best_practice
component: tooling
severity: medium
applies_when:
  - "Adding a comic source hosted on the artist's own site rather than a syndication CDN"
  - "A source serves its image over plain HTTP, or you're about to add a proxy to force HTTPS"
  - "A source has no archive: one image at a fixed path overwritten in place each day"
  - "Writing or reviewing a Netlify image proxy (or any server-side fetch of a caller-supplied URL)"
  - "Images render in a native RSS app but are blank in a web reader"
tags:
  - mixed-content
  - https
  - image-proxy
  - ssrf
  - rss-feed
  - feed-window
  - netlify-functions
  - comic-source
---

# Adding a self-hosted comic source — image hosting, feed shape, and proxy safety

## Context

ComicCaster adds sources as scraper/generator pairs (Phase 1 fetch → `data/<src>_$DATE.json`; Phase 2 network-free → `public/feeds/*.xml`). Most existing sources (GoComics, Comics Kingdom, Far Side) come with HTTPS image CDNs, dated metadata, and **distinct per-strip image URLs**. A *self-syndicated* comic hosted on the artist's own small site breaks all three assumptions at once.

Adding **Mr. Boffo** (issue #153) surfaced three decisions that recur for any such source — *where the image is hosted, what shape the feed can take, and how to safely reach a non-HTTPS asset*. They constrain each other, so solve them in order: hosting first (a reuse-vs-build decision), then feed shape, then — only on the residue — proxy safety.

## Guidance

### 1. Prefer an existing publisher HTTPS URL over running your own service

The reflex on hitting an HTTP-only image is to write a proxy that re-serves it over HTTPS. Resist it. Resolution order:

1. **Look for a sibling HTTPS host first.** Mr. Boffo is reachable at both `mrboffo.com` (HTTP image) and `mrboffocomics.com` (HTTPS image, same daily strip). Sourcing from `mrboffocomics.com` made the mixed-content problem vanish with zero infrastructure — no function, no SSRF surface, no cold-start, no egress.
2. **Only if no HTTPS source exists, add a proxy** — and accept that you now operate a network service with its own threat model (§3).

A self-hosted proxy is a liability you operate; a publisher's HTTPS URL is hosting you get for free. Reuse beats build.

**Catch the mixed-content failure correctly — it doesn't fail uniformly:**
- Native desktop/mobile readers (Reeder) load `http://` images fine (no HTTPS page context), so they **mask** the bug.
- A `curl -I http://…/image.jpg` only checks that the image is *fetchable* (it is). It misses the real failure: a browser / web reader **refusing to render an HTTP image inside an HTTPS page**.

The reliable check is to render the feed image in an HTTPS page context (a browser web reader, or the site's own Feed Preview served over HTTPS) and watch for a mixed-content block — not to fetch the bytes.

### 2. Let the source's archive shape set the feed window

A fixed image path overwritten daily, with no archive, means exactly **one** retrievable strip exists at any moment: today's. A multi-day window is physically impossible — every entry would resolve to the same (latest) bytes. So:

- Set `FEED_WINDOW = 1`. One-day-only is the **ceiling**, not a tuning choice.
- Give each day a distinct, stable identity via **fetch-date dating** (`guid = <src>-<date>`, `pub_date` = noon Eastern on capture day). Distinct dates → distinct pub_dates → no dedup collisions, and subscribers still get one new item per day. (This reuses the Far Side "daily dose" model — selection happens upstream, we just record the day.)
- Add a **date cache-buster** to the image URL so a reader that cached the fixed path yesterday refetches today's bytes: `f"{image_url}?d={target_date}"`.

**Contrast with Far Side**, which *does* have distinct per-strip asset URLs — so a multi-day window works there and needs no cache-buster. Read the source's asset model before copying another source's window.

### 3. If you must run a proxy, harden it against SSRF

A public, unauthenticated Netlify function that fetches a caller-supplied URL is an SSRF target. Validate strictly (see `functions/proxy-farside-image.js`, `functions/proxy-mrboffo-image.js` was removed once HTTPS sourcing replaced it):

- **Exact parsed hostname, never substring.** Parse with `new URL()` and match `parsed.hostname` against an allowlist. `imageUrl.includes('site.com')` accepts `site.com.evil.com`.
- **Scheme check.** Reject anything that isn't `http:`/`https:` (blocks `file:`, `gopher:`, …).
- **`redirect: 'manual'`** on the fetch, so an allowed host can't 30x-bounce you to an internal target.
- **`image/*` responses only**, so the proxy can never become a general-purpose content relay.

### 4. Register branding so the feed title reads right

A new source falls through `feed_generator.py`'s `source_display` map to the `"GoComics"` default, producing e.g. `Mr. Boffo - GoComics`. Add the source's *publisher* label to that map (`'mrboffo': 'Neatly Chiseled Features'`) — the slot is the publisher, not the comic name (avoid `Mr. Boffo - Mr. Boffo`). The one-off custom scrapers (`farside-daily`, `farside-new`) had the same latent gap.

## Why This Matters

- **You avoid operating a service you don't need.** Each Netlify function is an always-on attack surface, an egress cost, and a cold-start tax. Picking the publisher's HTTPS host deleted all of that.
- **You catch a bug tests and curl can't see.** Mixed-content blocking is invisible to offline unit tests, to native readers, and to a hotlink `curl`. Knowing it manifests *only in an HTTPS page context* is the difference between shipping silently-broken images to web-reader subscribers and catching it before push — and `main` ships live.
- **You shape the feed from reality, not habit.** Copying a multi-day window onto a single-overwritten-image source emits several entries all resolving to the same image — duplicate-looking strips and confused dedup.
- **A naive proxy is a real SSRF hole.** A substring host check on a public endpoint lets an attacker make your function fetch arbitrary internal/third-party URLs. The hardening is cheap; the hole is not.

## When to Apply

- Adding any comic hosted on the **artist's/publisher's own site** rather than a syndication CDN.
- The source serves images over **HTTP**, or you're about to write a proxy "to be safe" — look for an HTTPS sibling host first.
- The source has **no archive / no per-day permalink / a fixed image path overwritten in place** — before choosing a feed window.
- **Writing or reviewing any Netlify image proxy** or other server-side fetch of a caller-supplied URL.
- Diagnosing a feed whose images **render in a desktop reader but break in a web reader** — suspect mixed content; verify in an HTTPS page context, not with curl.

## Examples

**Mixed content: pick the HTTPS host, skip the proxy.**

```python
# BEFORE — reflexively HTTP source + a proxy to "fix" HTTPS:
#   image_url = "http://www.mrboffo.com/images/daily/...jpg"
#   feed_url  = f".../proxy-mrboffo-image?url={quote(image_url)}"
#   → a whole serverless function to own, plus its SSRF surface

# AFTER — comiccaster/mrboffo_scraper.py: a sibling HTTPS host already exists
BASE_URL = "https://www.mrboffocomics.com"   # serves the same strip over HTTPS
# No proxy. No function. Mixed content can't occur.
```

**Single overwritten image: window=1 + cache-buster + fetch-date dating.**

```python
# BEFORE — copying a multi-day source's pattern onto a fixed-path source:
#   FEED_WINDOW = 7
#   → 7 entries that ALL resolve to today's overwritten image

# AFTER — scripts/generate_mrboffo_feeds.py
FEED_WINDOW = 1                                    # archive can serve only "today"
cache_busted_url = f"{image_url}?d={target_date}"  # defeat reader cache of the fixed path
entries.append({
    'image_url': cache_busted_url,
    'pub_date': pub_datetime,                      # noon Eastern, distinct per day
    'id': f"mrboffo-{target_date}",                # one new guid per day
})
```

**Proxy SSRF hardening: exact hostname, not substring.**

```javascript
// BEFORE — substring check is an SSRF bypass:
//   if (imageUrl.includes('thefarside.com')) { /* fetch it */ }
//   → accepts http://thefarside.com.evil.com/  and  http://evil/?x=thefarside.com

// AFTER — functions/proxy-farside-image.js
const parsed = new URL(imageUrl);                       // parse, don't string-match
if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return forbidden();
const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
if (!allowedHosts.includes(host)) return forbidden();   // exact host allowlist
const response = await fetch(parsed.toString(), { redirect: 'manual', headers });
const ct = response.headers.get('content-type') || '';
if (!ct.toLowerCase().startsWith('image/')) return unsupportedMediaType();
```

## Related

- GitHub issue #153 — the Mr. Boffo request that originated this work (closed).
- `comiccaster/mrboffo_scraper.py`, `scripts/generate_mrboffo_feeds.py` — the reference implementation of §1–§2.
- `functions/proxy-farside-image.js` — the proxy pattern (Far Side genuinely needs one: its images require a `Referer`), with the §3 hardening applied.
- `comiccaster/feed_generator.py` — `source_display` branding map (§4) and single- vs multi-image description rendering.
- Disambiguation: `docs/solutions/logic-errors/gocomics-spanish-english-feed-contamination.md` discusses feed-*merge* overwrite semantics — a different "overwrite" from this doc's intentional single-image overwrite.
