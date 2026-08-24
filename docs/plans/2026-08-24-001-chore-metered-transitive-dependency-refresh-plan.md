---
artifact_contract: ce-unified-plan/v1
artifact_readiness: ready
execution: ops
title: "chore: refresh the host venv's transitive dependencies in metered stages"
date: 2026-08-24
type: chore
depth: standard
github_issues: []
related_docs:
  - docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md
  - docs/LOCAL_AUTOMATION_README.md
  - requirements.txt
---

# chore: metered transitive dependency refresh

## Status

**Stage 0 and Stage 1 complete 2026-08-24. Stages 2-4 pending, one per day.**

Written after a dependency sweep found the host venv's `certifi` five months
stale. Deliberately staged rather than done in one pass, because these packages
sit directly under the scrapers.

### Progress log

| Stage | Date | Result |
|---|---|---|
| 0 — baseline | 2026-08-24 | `docs/internal/venv-baseline-2026-08-24.txt`, 50 packages, captured after syncing venv to main (feedgen 1.0.0, selenium 4.47.0). |
| 1 — certifi | 2026-08-24 | 2026.2.25 → 2026.7.22. `pip freeze` diff = exactly one line. Gate: 491 passed; 0 TLS failures across all 7 sources + the CK B2C login host; feed-regen diff 502/506 byte-identical. |
| 2 — lxml, soupsieve | pending | earliest 2026-08-25, 09:00-11:00 |
| 3 — urllib3, idna, charset-normalizer | pending | after Stage 2 is observed clean |
| 4 — remainder | pending | after Stage 3 |

**Note on the Stage 1 feed diff:** 4 of 506 feeds differed — `shoe`,
`broomhilda`, `edge-city`, `pluggers`. This is **not** attributable to certifi.
Those four slugs are scraped by both GoComics and Comics Kingdom, both
generators write `public/feeds/<slug>.xml`, and the last writer wins. It is a
pre-existing collision, tracked separately; see the "Incidental finding" section
below. The remaining 502 were byte-identical, so the certifi gate is clean.

A further 145 committed feeds had no regenerated counterpart — expected, since
generators only emit feeds for comics present in that day's scrape, and the
pipeline leaves untouched feeds in place.

## Summary

`requirements.txt` pins **direct** dependencies only. Everything underneath them —
`certifi`, `urllib3`, `lxml`, `soupsieve`, `idna`, … — floats. `pip install -r
requirements.txt` will not advance a transitive dep that is already installed and
still satisfies its range, so the host venv only moves when something forces it.

Consequence: **the venv is not reproducible from anything in the repo.** Two
machines installing the same `requirements.txt` on different days get different
transitive sets, and no artifact records which set production is actually running.

Nothing is broken today. This is maintenance, and it should stay boring.

## Why not just upgrade everything

`pip install --upgrade` across all 16 would move `lxml`, `soupsieve`,
`charset-normalizer`, and `urllib3` in one step. Those four decide how HTML is
parsed, how CSS selectors resolve, how bytes become text, and how connections are
pooled. A scraper regression from that set does not raise — it silently returns
fewer entries or wrong fields, which is precisely the failure mode the invariant
guard exists to catch *after the fact*.

Staging costs a few days and makes any regression attributable to one group.

## The current gap

| Package | Installed | Latest | Sits under |
|---|---|---|---|
| certifi | 2026.2.25 | 2026.7.22 | requests, selenium — **CA bundle** |
| urllib3 | 2.6.3 | 2.7.0 | requests, selenium |
| idna | 3.11 | 3.19 | requests |
| charset-normalizer | 3.4.6 | 3.5.1 | requests |
| lxml | 6.0.2 | 6.1.2 | beautifulsoup4 |
| soupsieve | 2.8.3 | 2.9.2 | beautifulsoup4 |
| trio | 0.33.0 | 0.34.0 | selenium |
| tzlocal | 5.3.1 | 5.4.4 | APScheduler |
| Werkzeug | 3.1.6 | 3.1.8 | flask |
| click | 8.3.1 | 8.4.2 | flask |
| coverage | 7.13.5 | 7.15.4 | pytest-cov |
| Pygments / packaging / typing_extensions / pip | — | — | tooling |

## Scheduling constraint

Pass 1 runs 03:05, Pass 2 runs 13:00 (GoComics only). **Do each stage late
morning**, roughly 09:00–11:00. That is after Pass 1 has proven the day's scrape
and leaves ~2 hours to observe or roll back before Pass 2. Never stage in the
evening: a regression then gets its first real exercise at 03:05 unattended.

One stage per day. Do not batch two stages because the first looked fine.

## Verification gate (identical for every stage)

A stage is accepted only if all four pass:

1. `venv/bin/python -m pytest -q` → 491 passed
2. A **live single-source scrape** for the stage's blast radius, writing to a
   throwaway dir, then compare entry count against `SOURCE_RULES` minimums and
   against the last few days in `data/`.
3. Regenerate a feed from existing `data/*.json` into a temp `output_dir` and
   **diff the XML against the committed `public/feeds/*.xml`**. Byte-identical
   modulo timestamps, exactly as done for the feedgen 1.0.0 bump.
4. The next scheduled run completes and `check_scrape_counts.py` is clean.

Record the installed version set after each accepted stage.

## Stages

### Stage 0 — capture the baseline (do first, same day)

```bash
venv/bin/python -m pip freeze > docs/internal/venv-baseline-2026-08-24.txt
```

Without this there is nothing to roll back *to* — that is the actual reason the
current drift is hard to reason about. Commit it.

### Stage 1 — certifi only

Highest value, lowest risk: a CA bundle is data, with no API surface to break. A
stale bundle is a real, if latent, failure mode — a source rotating to a newly
cross-signed root starts failing TLS on a box this old.

```bash
venv/bin/python -m pip install --upgrade certifi
```

Gate: full suite, plus one live HTTPS fetch against each of the seven sources
(cheap — a `HEAD`/short `GET` per host is enough to exercise cert validation).

### Stage 2 — parsing layer: lxml, soupsieve

The group most likely to change scraper output, so it gets its own stage and the
most attention. Run the gate against **Comics Kingdom** (fixed catalog of 153 —
a partial parse is detectable with a tight floor) and **Creators** (stable 10).

### Stage 3 — HTTP layer: urllib3, idna, charset-normalizer

Gate against **GoComics** (largest surface, 210–282/day) and **TinyView**.
Watch for encoding regressions in titles rather than counts — a mangled title
still counts as an entry.

### Stage 4 — the rest: trio, tzlocal, Werkzeug, click, coverage, Pygments, packaging, typing_extensions, pip

Off the scraper hot path. `tzlocal` is the only one worth a second look, since
APScheduler uses it for timezone resolution and this pipeline is timezone-heavy
(Eastern-dated snapshots). Confirm `parse_date_with_timezone` behavior is
unchanged.

## The structural fix (do after Stage 4)

Staged upgrades fix today's drift; they do not stop it recurring. Once the set is
current, freeze it:

```bash
venv/bin/python -m pip freeze > constraints.txt
# thereafter:
venv/bin/python -m pip install -r requirements.txt -c constraints.txt
```

That makes the host environment reproducible and turns transitive movement into a
reviewable diff instead of an invisible one. `requirements.txt` keeps expressing
intent; `constraints.txt` records what production actually runs.

Open question for the operator: whether CI should also install with `-c
constraints.txt`. Doing so makes CI faithful to production, but costs the early
warning that comes from CI testing against newer transitives than the host has.
A reasonable split is CI unconstrained (canary) and the host constrained
(stability) — with a CI failure that the host does not reproduce read as "a
transitive broke us, investigate before the next refresh."

## Rollback

Per stage, from the Stage 0 baseline:

```bash
venv/bin/python -m pip install -r docs/internal/venv-baseline-2026-08-24.txt
venv/bin/python -m pytest -q
```

If a regression is found only after a bad feed is committed and pushed, the feed
data recovery path in `local_master_update.sh` (Phase 3) already handles
regenerating from authoritative scrape JSON — the scraped data is intact even
when the generated XML is wrong.

## Explicitly out of scope

- Pinning transitives in `requirements.txt` itself. That conflates "what we
  depend on" with "what resolved" — `constraints.txt` is the right separation.
- Adding a venv-drift preflight to the pipeline. Worth considering later, but it
  needs a decision on warn-vs-fail first, and a noisy new alert is worse than the
  drift it reports.


## Incidental finding (not part of this plan)

The Stage 1 feed-diff harness surfaced a pre-existing, subscriber-visible bug.

`shoe`, `broomhilda`, `edge-city`, and `pluggers` are the **only 4 slugs scraped
by both GoComics and Comics Kingdom**. Both generators write
`public/feeds/<slug>.xml`, so the last generator to run owns the file:

- **Pass 1 (03:05)** runs GoComics (`local_master_update.sh:232`) then Comics
  Kingdom (`:241`) — Comics Kingdom wins.
- **Pass 2 (13:00)** runs GoComics **only** (`local_pass2_update.sh:173`) — and
  Comics Kingdom never runs to reclaim the file, so GoComics wins.

Confirmed in git history — the first `<guid>` in `shoe.xml` alternates perfectly,
every day, for as far back as checked:

```
08-24 03:21  comicskingdom.com
08-23 13:02  www.gocomics.com
08-23 03:20  comicskingdom.com
08-22 13:02  www.gocomics.com
...
```

Because the `<guid>`, `<link>`, and image URLs all change with the source, RSS
readers see each flip as **new items** — subscribers to these 4 comics get every
strip delivered twice a day from alternating sources.

Fixing it needs a product decision (which source owns each of the 4 slugs), so it
is deliberately not bundled into a dependency refresh.
