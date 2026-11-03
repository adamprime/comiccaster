---
title: GoComics renamed its CSS-module classes — the scraper found 0 comics and blamed Bunny Shield
date: 2026-11-03
category: logic-errors
module: scrapers
problem_type: external-site-change
component: authenticated_scraper_secure.py
severity: high
applies_when:
  - "GoComics scrape logs 'Comic containers not found after waiting' on every custom page"
  - "The log says 'Page is a CDN bot challenge (Bunny Shield)' but /tmp/gocomics_debug_<date>.html is hundreds of KB and titled 'Comics from X | GoComics'"
  - "The invariant guard reports 'GoComics: only 0 entries'"
tags: [gocomics, css-modules, selectors, bunny-shield, false-positive, invariant-guard]
stack: [python, selenium, beautifulsoup]
github_issues: [254]
---

## TL;DR

Between the 2026-11-02 13:00 Pass 2 and the 2026-11-03 03:05 Pass 1, GoComics
changed how its build names CSS-module classes:

| Element | Before | After |
|---|---|---|
| comic container | `ComicViewer-module-scss-module__x__comicViewer` | `FfaN_W_comicViewer` |
| "didn't update today" section | matched by `FeaturesNotIssued` | `kf5J4a_featuresNotIssued` |

The scraper matched the old *file-name prefix* (`ComicViewer`, capital C), which
no longer appears anywhere on the page, so every favorites page yielded 0 comics.
The fix matches the CSS-module *local name* (`comicViewer`, `featuresNotIssued`),
the part both naming schemes keep. The hash prefix (`FfaN_W_`) can change on any
GoComics deploy; never match on it.

A second bug made the log lie about the cause: the challenge detector treated any
`/.bunny-shield/` path as the interstitial, and real GoComics pages now load
Bunny's fingerprinting script `/.bunny-shield/bd/bunnyprint.js`. The markers are
now the interstitial's title and its `shield-templates-prod.b-cdn.net` iframe.

## What the failure looked like

```
Scraping: https://www.gocomics.com/profile/User52732/comics/221821
  ⚠️  Comic containers not found after waiting
  ❌ Page is a CDN bot challenge (Bunny Shield), not GoComics content. ...
  ⚠️  No comic containers found. Page source saved to /tmp/gocomics_debug_2026-11-03.html
  Extracted 0 comics
  ... (same for all six pages)
✅ SUCCESS! Extracted 0 comics for 2026-11-03
```

The invariant guard caught it (`GoComics: only 0 entries, expected at least
100`) and opened #254. Published feeds were untouched; they just gained nothing.

## How it was diagnosed

1. The debug page was 577 KB with title `Comics from X | GoComics` and real strip
   images. A real interstitial is ~2 KB and titled *Establishing a secure
   connection ...*. **Check the size and title before believing the challenge
   message.**
2. `ComicViewer` occurred 0 times in the HTML; class names containing
   `comicViewer` were all of the form `FfaN_W_comicViewer[__layout|__footer|__rerun]`.
   Links (`/ziggy`) and strip URLs (`featureassets.gocomics.com/assets/…`) were
   unchanged.
3. Running `extract_comics_from_page` offline on the saved page with only the
   class match changed: 3 of 3 comics extracted, and the page's own cross-check
   agreed (`3 updated, 5 not updated today`).
4. The fixed scraper, run live at 07:53 against a scratch `--output-dir`,
   extracted 246 comics across all six pages, each page's cross-check matching.

## Gotcha: tests overwrite the debug page

`extract_comics_from_page` writes `/tmp/gocomics_debug_<date>.html` whenever it
finds no containers, and that includes unit tests using the same date string.
Here the red run of the new tests (dated 2026-11-03) replaced the real saved
page with test HTML. **Copy the debug page somewhere safe before running tests.**

## Recovery

Land the fix before Pass 2 (13:00). Pass 2 re-scrapes all six pages with
`--merge`, fills the day's file, and its success dispatch closes the issue.
