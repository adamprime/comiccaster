# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Sources

### Source
A comic provider ComicCaster pulls strips from. Each comic carries a `source` tag (e.g. GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, Mr. Boffo) that selects how it is fetched and where its feed link points.

### Self-hosted-feed source
A Source that ComicCaster scrapes itself and whose RSS feed ComicCaster generates and hosts (the feed lives at `/feeds/<slug>.xml`). Most sources are this kind. Contrast with an External-RSS source.

### External-RSS source
A Source that already publishes its own native RSS feed; ComicCaster simply points subscribers at that publisher feed URL and runs no scrape/generate pipeline for it.

## Pipeline

### Scrape phase
The network-facing first phase of the daily update: each source is fetched and parsed, writing a dated JSON snapshot per source. The only phase that touches the live comic sites.

### Generate phase
The network-free second phase: each source's generator reads its latest scraped JSON and writes the feed XML. Safe to re-run during recovery because it never hits the network.

### Invariant guard
The check between the Generate phase and the commit/push phase that asserts every scrape which reported success actually wrote its dated JSON snapshot; a missing file is surfaced as a failure rather than silently shipping a stale feed.

## Feed shaping

### Daily Dose
A dating model for sources that have no per-day permalink: the day's strip selection is made upstream by the publisher, and ComicCaster records it dated by fetch date rather than by the strip's own publication date. Used by The Far Side and Mr. Boffo.

A source whose image lives at a single fixed path overwritten in place each day has no retrievable history, so its feed holds only the current strip (a Feed window of one) and relies on fetch-date identity to give each day a distinct entry.

### Feed window
The number of recent days of strips a generated feed includes. Bounded by what the source's archive can actually serve: a source with distinct per-strip URLs supports a multi-day window, while a single-overwritten-image source supports a window of one.
