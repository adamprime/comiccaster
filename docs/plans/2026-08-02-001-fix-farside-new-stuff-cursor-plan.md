---
artifact_contract: ce-unified-plan/v1
artifact_readiness: needs-decision
execution: code
title: "fix: Far Side New Stuff feed has been empty since launch — bot protection blocks the scraper"
date: 2026-08-02
type: fix
depth: standard
github_issues: []
related_docs:
  - scripts/scrape_farside.py
  - comiccaster/farside_scraper.py
  - docs/solutions/best-practices/verify-postconditions-not-success-signals.md
  - docs/solutions/logic-errors/power-outage-launchagents-never-load.md
---

# fix: Far Side New Stuff feed has been empty since launch

## Status

**Root cause identified 2026-08-02. Not yet fixed — needs a product decision first.**

Found incidentally while verifying repo state after the power-outage catch-up run.
Unrelated to that outage.

## Summary

`public/feeds/farside-new.xml` contains **0 items and effectively always has**. Of the
**284 commits** touching the file, only **5** were ever non-empty — all on
**2025-11-20**, the day it was created, each with exactly **1** item. It has been
empty every day since 2025-11-21 (~8.5 months).

**Primary cause: thefarside.com now serves a bot-protection interstitial on
`/new-stuff/*`, and our headless scraper never gets past it.**

```
$ # Selenium load of https://www.thefarside.com/new-stuff/363/club-gombe
t~  5s bytes=1894 elems=26 | Hold tight  We are establishing a secure connection.
t~ 40s bytes=1894 elems=26 | Hold tight  We are establishing a secure connection.
```

The challenge does **not** clear with time (tested to 40s). The real page never
loads: 1,894 bytes, 26 elements, zero anchors, zero buttons, zero SVG.

Operator confirmed in a normal desktop browser that the section is alive and
**shows ~10 comics with working prev/next arrows** — a real browser clears the
challenge, ours does not.

### This is NOT a stale selector

The initial hypothesis was that a site redesign broke the `.js-next` arrow selector
in `comiccaster/farside_scraper.py:317-327`. **That was wrong.** The arrows are absent
from our DOM because *the comic page itself* is absent — we are parsing a challenge
page. Do not "fix" the selectors; they are untested against the real markup and
their correctness is currently unknowable.

### Why it reports success anyway

`scrape_new_stuff()` derives the comic id from `driver.current_url` via
`re.search(r'/new-stuff/(\d+)/([^/]+)', ...)` — **never from page content**. The
challenge page preserves the URL, so the walker happily extracts `363` from a page
containing no comic, finds no next arrow, exits after **0 clicks**, and returns one
content-free entry.

The pipeline then reports Far Side ✅, because the invariant only asserts that
`data/farside_new_$DATE.json` **exists** — and it does, containing `"comics": []`.
Textbook case of the trap in
`docs/solutions/best-practices/verify-postconditions-not-success-signals.md`.

### Daily Dose is unaffected

`farside-daily` uses plain `requests` against `/YYYY/MM/DD` and is **healthy** —
`data/farside_daily_2026-08-02.json` has real comics (id `22546`, live image URL).
Only `/new-stuff/*` is protected. Note plain `requests` to `/new-stuff/<id>` returns
**403** for every id tried (340, 363, 364, 380, 396, 400), so there is no non-browser
fallback for that path.

## Feasibility probes (2026-08-02) — what does NOT work

Negative results, recorded so they are not repeated. All three still return the
1,894-byte "Hold tight" interstitial:

| Probe | `navigator.webdriver` | Result |
| --- | --- | --- |
| Bare headless (current code) | `true` | blocked |
| Headless + fresh persistent `--user-data-dir` | `true` | blocked |
| Headless + profile + full CK/TinyView anti-detection flags | **`false`** | **still blocked** |

The third probe used exactly the pattern that works for Comics Kingdom and TinyView
(`scripts/comicskingdom_scraper_individual.py:84-86`):

```python
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
```

It successfully hides the automation flag and **still does not get through**, so the
protection is keying on something other than `navigator.webdriver` — most likely
headless itself, or it requires a challenge-clearance cookie obtained by actually
solving the JS challenge.

Note `comiccaster/farside_scraper.py` currently sets **none** of these options — it
builds a bare headless driver. Adding them is necessary but demonstrably not
sufficient.

**Implication:** a headless-only solution is not viable. The remaining routes are
non-headless Chrome, and/or a **profile primed once by a human** clearing the
challenge so the clearance cookie persists — the same shape as the existing Comics
Kingdom / TinyView reauth ritual (`docs/AUTHENTICATED_SCRAPING_README.md`).

Cost to weigh: that would make Far Side a **third** scraper with a periodic manual
operator step. For a section that currently holds ~10 comics and appears not to have
gained new ones since setup, the ongoing ritual may exceed the value — worth deciding
deliberately rather than by default. Unknown until measured: how long a clearance
cookie survives, which sets the reauth cadence.

## Secondary defects (real, but currently moot)

Even with page access restored, three bugs would keep the feed broken. Fix only
after the access problem is solved, and only in light of decision 2 below.

1. **Cursor can regress** — `scripts/scrape_farside.py:169` guards with `!=`, not `>`,
   so a lower archive max overwrites a higher cursor. Observed `396 -> 363`.
2. **Cursor is never persisted** — `data/farside_new_last_id.txt` is tracked, but the
   pipeline stages only `data/*.json` and `public/feeds/*.xml`
   (`scripts/local_master_update.sh:382`, `:447`), so the next run's
   `git reset --hard` reverts it. Every snapshot shows `cursor_before: 396`
   regardless of what the previous run wrote.
3. **Re-seed can never fire** — `scripts/scrape_farside.py:149` tests
   `feed_path.exists()` rather than whether the feed has *entries*. The file exists
   and is empty, so `is_initial` is permanently `False`.

## Open decisions

1. ~~**Is this feed worth restoring at all?**~~ **RESOLVED 2026-08-02 — keep it.**
   Operator: *"we should leave it up... it's important to not lose that
   functionality, and it sounds like we'll need a browser based solution."*
   Deleting `farside-new` is off the table. A browser-based approach is endorsed.

   Operator also observed that **no new comics appear to have been published since
   the original scraper was set up**. That is consistent with the empty feed and
   means a working scraper would likely emit nothing *new* — but it should still
   carry the ~10 comics that already exist, so subscribers get a populated feed
   rather than an empty document. Treat "feed contains the existing back catalogue"
   as the success criterion, not "feed gains new items".

2. **If restoring: is New Stuff an archive or a rotating single?** The operator sees
   ~10 comics behind arrows, which suggests a browsable archive with monotonic ids —
   in which case defect 1's `>` guard is correct. But **if it is a small rotating
   window**, ids will move both directions (396 then 363) and a `>` guard would
   *permanently suppress* every lower-id comic — strictly worse than today. Confirm
   which before touching the cursor comparison.

   **Evidence gathered 2026-08-25 — the "396 then 363" case is real, and intermittent.**
   The dated scrape files record the cursor move explicitly. Across the last 14 days:

   ```
   08-12..08-20  396 -> 396   comics=0     (11 of 14 days: no movement)
   08-21         396 -> 363   comics=0
   08-24         396 -> 363   comics=0
   08-25         396 -> 363   comics=0
   ```

   So ids **do** move backwards, exactly the pattern that would make a `>` guard
   permanently suppress lower-id comics. But this does **not** settle the decision,
   and should not be treated as proof of a rotating window: `comics` is empty on
   every one of those days, so the scraper was blocked each time, and a `363` parsed
   off a challenge interstitial is indistinguishable from a genuine lower id while
   the block persists. A constant artifact would likely appear every day rather than
   3 days in 14 — which is suggestive, not conclusive.

   **Decision 2 is therefore blocked on decision 3, not independent of it.** Clear the
   bot protection first; only then is the id trustworthy enough to classify.

   (Note the cursor file never persists: the pipeline `git reset --hard`s it at the
   start of every run, so it resets to 396 and re-moves each day. The 363 is never
   committed, which is why this was invisible until someone watched a run.)

3. **How to get past the challenge?** Prefer the approach this repo already uses for
   GoComics / Comics Kingdom / TinyView: a **persistent real Chrome profile** rather
   than a bare headless driver (see `docs/AUTHENTICATED_SCRAPING_README.md` and
   `docs/solutions/best-practices/scrapers-must-use-build-chrome-driver.md`). Those
   scrapers clear comparable protections today. Non-headless is a fallback. Do not
   add an evasion arms race for a feed nobody has missed.

## Proposed implementation (blocked on the decisions above)

1. **Test first**, per TDD — all offline with fixtures:
   - a challenge-page fixture must make `scrape_new_stuff()` **fail loudly**, not
     return a content-free entry (this is the defect that hid the problem for months)
   - the id must be parsed from **page content**, not solely from `current_url`
   - cursor must not regress; re-seed must trigger on an **empty** feed, not a missing one
2. Make the scrape assert a postcondition: a comic page must yield an image/title, or
   the source fails. Extend the pipeline invariant beyond "file exists" to
   "`comics` is non-empty" for this source.
3. Only then address the cursor defects, per decision 2.
4. Verify: `pytest -v` green, then a manual `python scripts/scrape_farside.py` yielding
   a non-empty `comics` array.

## Next session — start here

```bash
# Reproduce the blocker in ~30s (expect the "Hold tight" interstitial)
source venv/bin/activate
python - <<'PY'
from selenium.webdriver.chrome.options import Options
from comiccaster.webdriver_setup import build_chrome_driver
import time
o=Options()
for a in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--window-size=1920,1080']: o.add_argument(a)
d=build_chrome_driver(o)
d.get("https://www.thefarside.com/new-stuff"); time.sleep(5)
print(len(d.page_source), d.current_url)
print(d.execute_script("return document.body.innerText")[:200])
d.quit()
PY

# Current state
cat data/farside_new_$(date +%Y-%m-%d).json      # expect "comics": []
grep -c "<item>" public/feeds/farside-new.xml    # expect 0
```

`data/farside_new_last_id.txt` may show an uncommitted `396 -> 363` edit. That is
defect 2 above; it is expected to vanish on the next run's `git reset --hard`.
