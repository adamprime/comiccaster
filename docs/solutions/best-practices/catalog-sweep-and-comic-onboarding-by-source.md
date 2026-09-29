---
title: "Sweeping every Source's catalog for missing comics, and how to add one"
date: 2026-09-29
last_updated: 2026-09-29
category: best-practices
module: comic-sources
problem_type: best_practice
component: tooling
severity: medium
applies_when:
  - "Running the periodic sweep to find comics a Source publishes that our catalog is missing"
  - "Adding a newly discovered comic's catalog entry for TinyView, GoComics, Comics Kingdom, or Creators"
  - "A Source's listing page seems to show fewer comics than it carries (an undercounting parse, a guessed URL, a Bunny Shield 403)"
  - "Deciding whether a catalog entry alone is enough, or whether a Source also needs an operator action (e.g. GoComics favorites) before a comic gets a feed"
  - "Reconstructing the discovery method because prior tooling was deleted or nobody remembers the steps"
tags: [catalog, discovery, tinyview, gocomics, comicskingdom, creators, source-onboarding, nextjs-flight-payload]
stack: [python, json]
---

# Catalog sweep: finding comics a Source carries that we don't, and adding them

## TL;DR

Every multi-comic Source publishes its full comic list in a page that plain HTTP
with a desktop browser User-Agent can fetch. You don't need a login or Selenium.
To sweep, pull each list, diff it against `public/*_list.json`, and look up the
last post date of each gap. The traps are in *where* the list lives. TinyView's
cards and Comics Kingdom's links each undercount. The complete lists are in the
data embedded in each page.

Adding a comic is a catalog edit for TinyView and Comics Kingdom. GoComics also
needs the operator to favorite the comic, because its scraper never reads the
catalog. Build every new feed after Pass 2 and push it before the next Pass 1.
Otherwise the pipeline's own commit ships it unpreviewed.

## Context

The operator, on 2026-09-28: "It's been quite a while since we did a sweep... to
be honest, I can't even remember exactly how to do this."

The previous sweep was in Nov 2025. Commit 755c2e583c added Deogie! and Student
Bill "using the authenticated comic discovery script". Commit 53ee942c10
(2026-03-20, "Switch to Elastic License 2.0, clean up repo") deleted those
scripts:
`discover_tinyview_comics_authenticated.py`, `discover_tinyview_comics.py`,
`discover_tinyview_directory.py`, `discover_more_tinyview.py`,
`discover_creators_comics.py`, `discover_political_comics.py`,
`add_comicskingdom_to_catalog.py` and `add_favorites_to_catalog.py`. They drove
Selenium through the logged-in Chrome profile. Any of them can be recovered with
`git show 53ee942c10^:scripts/<name>.py`, but none is needed now. The 2026-09-28
sweep used plain HTTP for every Source.

Nothing in the tree implements this method, and no sweep ran for ten months.
The planned follow-up is a monthly automated sweep: a scheduled job on the
pipeline host that opens a GitHub issue when a Source lists comics we don't
carry. This doc is the method that job will implement.

## Guidance

### 1. Where each Source's full list lives

| Source | Full list | Diff it against | Excluded on purpose |
|---|---|---|---|
| TinyView | Series registry in the flight payload of `https://tinyview.com/tinyview/comic-series-directory`. Cadence per series: `https://cdn.tinyview.com/<slug>/index.json` | the **path of each catalog `url`**, not `slug` | `tinyview` (house account), `the-daily-show` (last post 2024-03) |
| GoComics | Flight payload of `https://www.gocomics.com/comics/a-to-z` **and** `https://www.gocomics.com/political-cartoons/political-a-to-z` | `slug` | `lunarbaboon` (TinyView owns it, PR #193) |
| Comics Kingdom | The `__NEXT_DATA__` blob of `https://comicskingdom.com/features`. For tab placement, also `https://comicskingdom.com/genre/political` (page 2: `?featurepage=2&feature_genre=political`) | `source_slug or slug` | `broomhilda`, `pluggers`, `shoe` (GoComics owns them, PR #193) |
| Creators | `/read/<slug>` links on `https://www.creators.com/categories/comics/all`, plus the verdicts in `data/creators_discovery_report.json` | `source_slug or slug` | every uncatalogued comic as of 2026-09-28 (see §4) |
| Far Side, New Yorker, Mr. Boffo | single feed each, nothing to discover | | |
| External RSS | hand-curated | | |

### 2. Pull the lists and diff them

Run this from the repo root with any Python 3.9+. It uses curl, which is what
passed GoComics' Bunny Shield on 2026-09-28. The desktop UA matters: Bunny
Shield refuses a `HeadlessChrome` UA (see
`docs/solutions/logic-errors/gocomics-bunny-shield-refuses-headless-chrome.md`).

```python
import glob, json, re, subprocess
from urllib.parse import urlparse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

def get(url):  # -f: an HTTP error (403, 404) raises instead of returning a page
    return subprocess.run(["curl", "-sfL", "-A", UA, url], check=True,
                          capture_output=True).stdout.decode("utf-8")

def walk(node):
    """Every dict nested anywhere inside a parsed JSON value."""
    stack = [node]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            yield node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)

def flight_objects(html):
    """Every JSON object in a Next.js App Router page's flight payload."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    payload = "".join(json.loads(c) for c in chunks)  # each chunk is a JSON string
    for row in payload.splitlines():                   # rows look like <id>:<json>
        _, sep, body = row.partition(":")
        if sep and body[:1] in "[{":
            try:
                yield from walk(json.loads(body))
            except ValueError:
                pass                                   # a text row, not JSON

# TinyView: the series registry, keyed by the slug inside "action"
tinyview = {}
for o in flight_objects(get("https://tinyview.com/tinyview/comic-series-directory")):
    m = re.fullmatch(r"/([^/]+)/index\.json", str(o.get("action", "")))
    if m and "title" in o:
        tinyview[m.group(1)] = o                       # o["credits"] == [{"By": author}]

# GoComics: strips and editorial are separate pages
gocomics = {}
for url in ("https://www.gocomics.com/comics/a-to-z",
            "https://www.gocomics.com/political-cartoons/political-a-to-z"):
    gocomics.update({o["slug"]: o for o in flight_objects(get(url))
                     if "slug" in o and "updatedToday" in o})

# Comics Kingdom: a Pages Router page, so one __NEXT_DATA__ blob
html = get("https://comicskingdom.com/features")
blob = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                 html, re.S).group(1)
kingdom = {o["slug"]: o for o in walk(json.loads(blob)) if "ck_feature_type_slug" in o}

# Creators: plain links
creators = set(re.findall(r'href="(?:https://www\.creators\.com)?/read/([a-z0-9-]+)"',
                          get("https://www.creators.com/categories/comics/all")))

catalog = [c for f in glob.glob("public/*_list.json") for c in json.load(open(f))]

def carried(source):  # a catalog entry with no `source` is GoComics
    return {c.get("source_slug") or c["slug"] for c in catalog
            if (c.get("source") or "gocomics") == source}

tv_paths = {urlparse(c["url"]).path.strip("/") for c in catalog if c.get("source") == "tinyview"}
print("TinyView      ", sorted(set(tinyview) - tv_paths))
print("GoComics      ", sorted(set(gocomics) - carried("gocomics")))
print("Comics Kingdom", sorted(set(kingdom) - carried("comicskingdom")))
print("Creators      ", sorted(creators - carried("creators")))
```

On the pages saved 2026-09-28, the parsers find 38 TinyView series, 464 GoComics
features (260 `updatedToday`), 160 Comics Kingdom features and 36 Creators
comics. Diffed against the 2026-09-29 catalogs, what's left is exactly the
exclusions in §1, the Creators duplicates, and `the-little-king` (see Examples).
Any other slug is a candidate. Check its last post date (§5) before you add it.

### 3. Traps, per Source

**TinyView**
- **Don't parse the rendered cards.** A card parse on 2026-09-28 found 23 of 38
  series. It missed active comics such as Fowl Language, Rob Rogers, Itchy Feet
  and Heart and Brain. A re-check of the saved page for this doc showed why. The
  cards have no links (navigation is a click handler), so the only slug on a card
  is inside its cover-image URL. Cover filenames vary (`cover.jpg`,
  `fowl-language-cover.jpg`, `HeartandBrain-cover.jpg`, `Cover.jpg`,
  `frankie-fearless-800x1000.jpg`), and a `/<slug>/cover.(jpg|png)` pattern
  matches exactly 23. Card titles don't match slugs either: "Creative Notes" is
  `connie` and "Bite Sized Archie" is `archie`. The registry in the flight
  payload lists all 38 series, with slugs.
- **Take slugs from the registry, never from the title.** Skull Pizza is
  `skullpizza`, and `https://tinyview.com/skull-pizza` is a 404.
- **Diff on the catalog `url` path, not `slug`.** The scraper fetches the path of
  `url` (`scripts/tinyview_scraper_local_authenticated.py:189-194`), and a feed
  slug can differ from that path: `fowl-language-tinyview` → `/fowl-language`,
  `matt-bors-tinyview` → `/matt-bors`.
- **Cadence:** `https://cdn.tinyview.com/<slug>/index.json` is public JSON. Its
  `comics.panels[]` entries with `"template": "toc"` are episodes. Each has a
  `datetime`, usually ISO but an RFC 2822 string on some older entries. Many also
  have `show-to` (`everyone` / `subscribers-only`). Dates can be in the future:
  on 2026-09-28 Gemma, This Modern World and Fowl Language had October posts
  already scheduled.

**GoComics**
- **Take listing URLs from `https://www.gocomics.com/sitemap.xml`.** Guessed URLs
  (`/political-cartoons`, `/comics/political-a-to-z`) returned 403. Here a 403
  can mean a wrong URL, not a bot block.
- Each feature object carries `slug`, `name`, `creators`, `categories`,
  `featureLanguage` (32 are Spanish) and `updatedToday`. `updatedToday` is what
  makes the coverage check in §5 possible.

**Comics Kingdom**
- **Don't scrape the `/features` links.** They come in three shapes:
  `/<slug>/<YYYY-MM-DD>`, `/vintage/<slug>/<date>`, and
  `/?post_type=ck_comic&p=<id>` (Lee Judge, Kirk Walters). A pattern for the
  first shape saw 122 of 160 features. It missed every vintage title and several
  editorial cartoonists. `__NEXT_DATA__` has all 160, each with
  `ck_feature_type_slug` (`comic` 87, `vintage` 34, `spanish` 31, `political` 8)
  and `ck_latest_comic.date`.
- **Match on slug, not the catalog `url`.** Catalog `url` fields vary
  (`/slug`, `/slug/2025-11-15`, `/?post_type=ck_comic&p=...`). Honour
  `source_slug`: `edge-city-classic` is CK's own run of Edge City, served at
  `edge-city`.
- **A vintage title's latest date is historical** (The Little King:
  1958-12-28), so it says nothing about whether the title is active.
- **CK labels editorial work in two places, and they disagree.** Feature type
  `political` covers 8 cartoonists. `/genre/political` also lists Mallard
  Fillmore and Willy Black, whose feature type is `comic`. Check both when
  choosing Daily or Political.

**Creators**
- `data/creators_discovery_report.json` (generated 2026-02-23 by the deleted
  `discover_creators_comics.py`) records, per comic, `eligible`,
  `slug_collision`, `name_overlap` and `active_recently`. Read its verdict before
  re-investigating a comic.

### 4. Known exclusions, so the next sweep doesn't re-add them

- **GoComics `lunarbaboon`**: TinyView owns it (PR #193).
- **Comics Kingdom `broomhilda`, `pluggers`, `shoe`**: GoComics owns them
  (PR #193). Edge City is on both, as two feeds, on purpose.
- **TinyView `tinyview` and `the-daily-show`**: the platform's own account, and a
  series dormant since 2024-03.
- **Comics Kingdom `ed-gamble` (last 2025-04) and `mike-shelton` (last
  2022-05)**: dormant, but the operator chose to keep them listed.
- **All 26 uncatalogued Creators comics**: in the report, 25 overlap a GoComics
  comic and 1 is inactive. Nothing to add.

### 5. A silent catalog entry: dormant or broken?

A catalog entry with no recent strips is either dormant upstream or missed by
our scraper. Measure which before touching any code.

**GoComics: `updatedToday` against the day's scrape.** The scraper only sees the
account's favorites pages. If it captured nearly every comic GoComics marks
`updatedToday`, the silent entries are dormant rather than a favorites gap:

```python
day = "2026-09-28"
scraped = {c["slug"] for c in json.load(open(f"data/comics_{day}.json"))}
updated = {s for s, o in gocomics.items() if o["updatedToday"]}
print(len(updated & scraped), "of", len(updated), "missed:", sorted(updated - scraped))
```

Late publishers flip to `updatedToday` after the 03:05 Pass 1. Compare against
the data file after Pass 2 has merged, or expect a few misses that Pass 2 then
picks up.

**TinyView: newest episode date.**

```python
from datetime import datetime
from email.utils import parsedate_to_datetime

def last_post(slug):
    index = json.loads(get(f"https://cdn.tinyview.com/{slug}/index.json"))
    def when(s):  # ISO normally, RFC 2822 on some older entries
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            return parsedate_to_datetime(s).date()
    return max((when(p["datetime"]) for p in index["comics"]["panels"]
                if p.get("template") == "toc" and p.get("datetime")), default=None)
```

**Comics Kingdom:** `kingdom[slug]["ck_latest_comic"]["date"]`, for
non-vintage titles only.

### 6. Adding a comic

**Every Source**
1. **Check the slug isn't already a feed path.** Run
   `pytest tests/test_catalog_source_integrity.py`. It checks that no slug is
   claimed by two feed-generating Sources (`:117`), that `url` names the
   `source`'s host (`:93`), and that no slug is in both the Daily and Political
   lists (`:212`). If two Sources carry the same comic, compare the actual strips
   before choosing (CONCEPTS.md, *Source slug*).
2. **Build after Pass 2 (13:00 CT) and push before Pass 1 (03:05).** Both passes
   start with `git reset --hard origin/main` (`scripts/local_master_update.sh:140`,
   `scripts/local_pass2_update.sh:149`). The reset reverts an uncommitted catalog
   edit but leaves untracked files. Each pass then force-adds every feed:
   `git add -f public/feeds/*.xml` (`local_pass2_update.sh:121`), and Pass 1 adds
   `data/*.json` too (`local_master_update.sh:414`). A feed you built
   earlier ships in the pipeline's commit, unpreviewed.
3. **The operator previews each feed before it ships.** A deploy preview can't
   show an un-merged feed. Render the feeds instead with
   `python scripts/preview_feeds.py public/feeds/<slug>.xml --against origin/main --open`.
   It writes one HTML page with every item's guid, date, link and images. It flags
   duplicate or missing guids, and it marks each item new, changed or missing
   against `main`. Raw XML in codebeautify.org/rssviewer also works, but that
   viewer shows no images (auto memory [claude]).
4. Commit the catalog edit (`feat:`) separately from the data and feeds
   (`chore:`), staging explicit paths.

**TinyView: catalog entry only**
- Add `{name, slug, author, url, source: "tinyview"}` to
  `public/tinyview_comics_list.json`, keeping the list sorted by name. The
  scraper reads this catalog. The `url` path must be the registry slug, because
  that path is what gets fetched.
- Build: `python scripts/tinyview_scraper_local_authenticated.py --date $DATE --days-back 90`,
  then `python scripts/generate_tinyview_feeds_from_data.py`.
- **Feed contents.** The pipeline lists 90 days of strips (`--days-back 90`,
  `scripts/local_master_update.sh:177`) and fetches each new one by its own
  address. The generator builds each feed from every strip dated within 90 days
  of the newest `data/tinyview_YYYY-MM-DD.json`, reading every data file
  (`WINDOW_DAYS` and `load_window_strips` in
  `scripts/generate_tinyview_feeds_from_data.py`). So a new comic's feed starts
  with its last 90 days of strips and keeps them as they age. A comic with no
  strip in that window gets no feed file, and its link on the site 404s until it
  posts again. An existing feed is never emptied. Until PR #212 the generator
  read only the newest file, so every TinyView feed held one strip; see
  `docs/solutions/logic-errors/tinyview-feed-history-collapsed-to-one-strip.md`.
- **The scraper records each strip once, by its address**, across all of
  `data/`. The run ends with `Listed but not recorded: N`; anything but 0 means a
  listed strip showed none of its own panels and will be retried the next night.
- **A same-day rerun merges into `data/tinyview_<today>.json`**
  (`merge_with_existing`, `scripts/tinyview_scraper_local_authenticated.py:266`);
  records already in the file win. It can pick up new strips for comics you
  didn't add, so commit that data file together with every feed it regenerated.
  Before PR #212 a feed left behind lost the strip for good (ee779fb6b2 shipped
  ADHDinos for this reason). Now the next night's regeneration picks it up, but
  shipping them together keeps each feed matched to its data.

**GoComics: two steps, both required**
- The scraper never reads the catalog. It reads the account's favorites pages,
  `CUSTOM_PAGE_<n>` plus optional `CUSTOM_PAGE_<n>_CATEGORY` in `.env`
  (`scripts/authenticated_scraper_secure.py:60-76`). At this writing page 1 is
  political and the rest are daily. The generator builds feeds only for catalog
  entries that have scraped data (`scripts/generate_gocomics_feeds.py:117-140`,
  `:154-155`). A comic that is only favorited gets data but no feed. A comic that
  is only catalogued gets a site listing whose link 404s.
  1. The operator favorites it on the right page while logged in.
  2. Add the catalog entry. Strips go in `public/comics_list.json`, with no
     `source` field. Append the entry at the end with `position` = max position
     + 1, not last + 1: Mr. Boffo holds 570 mid-file. Editorial cartoonists go in
     `public/political_comics_list.json`, copying a neighbour's shape.
- **First data.** Pass 2 re-scrapes every favorites page for today
  (`authenticated_scraper_secure.py:490`, with `--merge`). Its rolling backfill
  of past days covers political pages only (`:405`). A daily strip therefore gets
  its first data only if it shows as updated at one of the day's scrapes. A miss
  is not recovered later. If Pass 2 already captured it, running
  `python scripts/generate_gocomics_feeds.py` is enough.

**Comics Kingdom: catalog entry only**
- Add an entry with `source: "comicskingdom"` to `comics_list.json` or
  `political_comics_list.json`, never both. Since PR #208, both CK scripts load
  both lists through `load_comicskingdom_catalog`
  (`comiccaster/comicskingdom_catalog.py:22`). Set `source_slug` when CK's path
  differs from the feed slug. Vintage titles take `source_variant: "vintage"`, and
  their feeds are subject to the open issue #207.
- Keep the catalog size in the `SOURCE_RULES` note, and the ~94% floor, in step
  (`scripts/check_scrape_counts.py:45-46`), as e520b129fb did.

## Why This Matters

- **Gaps accumulate silently.** In ten months without a sweep, six active comics
  went uncarried. The same sweep found six Comics Kingdom cartoonists that had
  been listed and 404ing the whole time, while every run reported ALL SUCCESS.
- **The obvious sources undercount without raising an error.** A card parse of
  TinyView's directory gave 23 of 38 series, and CK's links gave 122 of 160. A sweep that reads them
  concludes "nothing new" and gets no signal that it is wrong.
- **Dormant and broken look identical from the catalog.** Without the
  `updatedToday` and `index.json` measurements, silent entries look like scraper
  bugs and invite fixes to code that works.
- **Adding a comic the wrong way fails quietly.** A GoComics comic that is only
  catalogued is a dead link. A feed built before Pass 2 reaches subscribers
  through the automation's commit before anyone has looked at it.

## When to Apply

- A periodic sweep: monthly, and eventually as the automated job.
- A reader asks for a comic, or a Source announces a new one.
- Before adding any comic to any catalog.
- A catalog entry has produced no strips for a while, and you need to know
  whether it is dormant or broken.
- Writing or reviewing the automated sweep job.

## Examples

### The 2026-09-28 sweep

| Source | Found | Outcome |
|---|---|---|
| TinyView | 38 registry series; 5 active and uncatalogued | Added Skull Pizza (`skullpizza`), Kowal Comics (`kowal-comics`), Mr. Lovenstein (`mrlovenstein`), Boids Adventures (`boids`), Graphic Rage (`graphic-rage`) |
| GoComics | 1 uncatalogued besides `lunarbaboon` | Added Sour Grapes (`sour-grapes`). The operator favorited it that morning, Pass 2 captured it at 13:00, and its feed was built after |
| Comics Kingdom | Nothing new; 6 political-tab cartoonists never loaded | The loader bug, fixed in PR #208; see `docs/solutions/logic-errors/comicskingdom-political-comics-never-loaded.md`. Issue #207 opened for dormant-feed re-delivery |
| Creators | 26 uncatalogued, all duplicates or inactive | Nothing added |

The catalog went out in commit 655e8165bb and the feeds in ee779fb6b2, built
after Pass 2 and previewed by the operator. Graphic Rage's last post was
2026-07-14, outside the scraper's then-effective 30-day lookup, so it shipped
listed without a feed. It got its first feed on 2026-09-29, from the catch-up
after PR #212 (commit a65f53186e).

### Dormant, not broken

- **TinyView, 14 series with zero scraped strips:** `biographic`, `matt-bors`,
  `say-their-names`, `olo`, `product-plug`, `connie`, `candy-hearts`, `thenib`,
  `caption-contest`, `bite-subscribe`, `quotes`, `cyanide-and-happiness`,
  `brief-histories` and `eggs-n-ben`. Their `index.json` last posts run from
  2021-03 to 2025-09. The cause is upstream dormancy, not the scraper.
- **GoComics, about 93 catalog entries absent from every 2026 scrape:** Pass 1's
  `data/comics_2026-09-28.json` held 256 of the 260 `updatedToday` comics. The
  four it lacked (`lards-world-peace-tips`, `sour-grapes`, `tinysepuku`,
  `two-party-opera`) were all in the file after Pass 2's merge. None of the
  silent entries was `updatedToday`, so this is dormancy, not a favorites gap.

### Found while writing this doc: The Little King

Running §2 against the saved 2026-09-28 `/features` page reports
`the-little-king` (vintage, Otto Soglow). It is in no catalog and is not a known
exclusion. The sweep's link-based pass couldn't see it, because its only link is
`/vintage/the-little-king/1958-12-28`. It is undecided as of this writing, and
adding it would give #207's vintage problem another feed.

## Related

- `docs/solutions/logic-errors/comicskingdom-political-comics-never-loaded.md`:
  the bug this sweep surfaced. Each catalog file is both a tab and a loader input.
- `docs/solutions/logic-errors/two-sources-one-feed-file-slug-collision.md` and
  PR #193: why the §4 exclusions exist, and `source_slug`.
- `docs/solutions/logic-errors/gocomics-favorites-page-timing.md`: why favorites
  coverage needs Pass 2.
- `docs/solutions/logic-errors/gocomics-bunny-shield-refuses-headless-chrome.md`:
  why the UA matters.
- `docs/solutions/best-practices/mixed-content-and-single-image-comic-sources.md`
  and `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`:
  adding a new *Source* (a scraper, generator and `SOURCE_RULES` entry), not a
  comic.
- `docs/plans/2026-09-28-1129-fix-catalog-sweep-ck-political-loader-plan.md`: the
  plan behind the 2026-09-28 work.
- `CONCEPTS.md`: *Catalog*, *Feed identity*, *Source slug*.
