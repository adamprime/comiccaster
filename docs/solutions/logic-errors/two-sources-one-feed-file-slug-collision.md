---
title: "Two sources, one feed file: a slug claimed twice flips the feed every pass"
date: 2026-08-24
category: logic-errors
module: pipeline
problem_type: silent-data-corruption
component: generate_gocomics_feeds.py / generate_comicskingdom_feeds.py / public/comics_list.json
severity: high
applies_when:
  - "A subscriber reports getting the same comic twice a day, or two interleaved storylines"
  - "A feed's <guid> and <link> alternate host between the 03:05 and 13:00 commits"
  - "Adding a comic that more than one source carries"
  - "Bulk-importing a source catalog by stamping `source` onto existing entries"
tags: [collision, slug, source-of-truth, catalog, gocomics, comicskingdom, feed-identity, reruns]
stack: [python, json]
github_prs: []
---

## TL;DR

Every self-hosted feed lives at `public/feeds/<slug>.xml`, so a slug may be
claimed by at most **one** feed-generating source. Four slugs were claimed by
two. Both generators wrote the same path, pass 1 ended with Comics Kingdom and
pass 2 ran GoComics alone, so the file alternated source twice a day forever.

## How it looked from outside

A subscriber to Edge City saw "two different storylines" interleaved and assumed
it was upstream weirdness. Nothing was logged, no invariant fired, and every
pipeline run reported ALL SUCCESS -- because every run *was* succeeding. It was
writing the file correctly; it just wasn't the same file contents as six hours
earlier.

Git history makes it obvious once you look at one feed across commits:

```
08-24 03:21  comicskingdom.com     <- pass 1 (GoComics then Comics Kingdom)
08-23 13:02  www.gocomics.com      <- pass 2 (GoComics only)
08-23 03:20  comicskingdom.com
08-22 13:02  www.gocomics.com
```

Because `<guid>` changes with the source, RSS readers treat each flip as a new
item. Subscribers got every strip twice a day.

## Root cause, in two layers

**1. The catalog was self-contradictory.** Commit `11e401b688`
("Add all Comics Kingdom comics", 2025-11-15) stamped `source: comicskingdom`
onto entries that already existed as GoComics comics and left their `url`
pointing at gocomics.com. The fingerprint -- `source` naming one host while
`url` names another -- matched exactly 5 entries out of 600+.

**2. Only one generator enforced ownership.** `generate_comicskingdom_feeds.py`
had always filtered `c.get('source') == 'comicskingdom'`.
`generate_gocomics_feeds.py` did not filter at all; `load_comics_catalog()`
loaded every entry and called it "the full GoComics catalog." So GoComics wrote
feeds for comics the catalog assigned elsewhere.

Neither layer is visible on its own. The catalog looked fine if you only read
`source`; the generator looked fine if you only read GoComics comics.

## Distinguishing the two cases -- this is the part that matters

When two sources carry "the same" comic, they are not necessarily carrying the
same *work*, and the right fix differs:

| | Same strip | Different runs |
|---|---|---|
| Example | Broom Hilda, Pluggers, Shoe | Edge City |
| Fix | pick ONE source, drop the other | give each run its OWN slug |
| Why | a second feed would duplicate | they are distinct works |

**Do not guess which case you are in.** Compare the images. Perceptual
correlation on downsampled greyscale is enough, and you need a *positive
control* to know what a match scores:

```python
from PIL import Image
def vec(path, n=64):
    px = list(Image.open(path).convert("L").resize((n, n), Image.LANCZOS).getdata())
    m = sum(px) / len(px)
    sd = (sum((p - m) ** 2 for p in px) / len(px)) ** 0.5 or 1e-9
    return [(p - m) / sd for p in px]
corr = lambda a, b: sum(x * y for x, y in zip(a, b)) / len(a)
```

Results that settled it:

- **Broom Hilda (control):** same-day r = **0.989-0.998**, best-match offset 0
  on all 10 sampled days. That is what "identical" looks like.
- **Edge City:** same-day r = 0.03-0.20, and the best match at *any* offset in a
  +/-16 day window was r = 0.33 -- the noise floor. No lag explains it.

The copyright line confirmed why: GoComics runs the **2011** sequence, Comics
Kingdom the **2006** one. Both are reruns of different vintages.

**A trap worth naming:** the printed date in the art (`7.10`, `7.7`) is
day-month only. It cannot distinguish a three-day lag from a five-year-old
rerun, and reading it that way produced a confidently wrong first diagnosis.
The copyright year and the image comparison are the evidence; the strip date is
not.

## The fix

- Catalog: the three identical comics went to GoComics (chosen on delivery
  reliability -- 83/83 days vs 79-80/83 for Comics Kingdom over Jun-Aug).
- Edge City keeps `edge-city` on GoComics so existing subscriptions survive, and
  Comics Kingdom's run became `edge-city-classic`.
- `generate_gocomics_feeds.py` grew `owned_by_gocomics()` and filters in
  `main()` -- deliberately *not* in `load_comics_catalog()`, because an existing
  test asserts that loader returns every entry from `public/` (that test guards
  the 2026-05-16 dual-catalog fix and must keep its meaning).
- New optional `source_slug`: the path a source serves the comic at, when it
  differs from the slug we file it under. Defaults to `slug`.

## Prevention

`tests/test_catalog_source_integrity.py` now asserts:

1. every entry declares a known source;
2. `source` and `url` name the same host -- this is what would have caught
   `11e401b688` on the day it landed;
3. no slug is claimed by two feed-generating sources.

All three are offline and run in the default suite.

## Key insight

A feed path is an identity. If two things can claim one identity, one of them is
silently destroyed on every run, and the pipeline will report success while
doing it -- the same shape as
`docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`. Assert
the uniqueness of identity in a test, because no amount of per-source
correctness gives it to you.

## Related

- `docs/solutions/logic-errors/gocomics-spanish-english-feed-contamination.md` --
  the same class one layer down (English/Spanish strips colliding on a
  badge-derived slug). Its "prefer canonical identifiers over derived ones" is
  what `source_slug` implements.
- `docs/plans/2026-05-16-001-fix-dual-catalog-source-of-truth-plan.md` -- why the
  ownership filter lives in `main()` and not the loader.
