# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Sources

### Source
A comic provider ComicCaster pulls strips from. Each comic carries a `source` tag (e.g. GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, Mr. Boffo) that selects how it is fetched and where its feed link points.

### Self-hosted-feed source
A Source that ComicCaster scrapes itself and whose RSS feed ComicCaster generates and hosts (the feed lives at `/feeds/<slug>.xml`). Most sources are this kind. Contrast with an External-RSS source.

### External-RSS source
A Source that already publishes its own native RSS feed; ComicCaster simply points subscribers at that publisher feed URL and runs no scrape/generate pipeline for it.

### Catalog
The lists that say which comics ComicCaster offers. Each list does two jobs at once: it is a tab on the website (Daily, Political, TinyView, Spanish, external), and it is an input that a Source's scrape and generate steps may or may not read. A comic's list decides which tab shows it; its Source decides who builds its feed.

The two jobs are independent, so a comic can sit on a tab that no loader for its Source reads. It then appears on the site with a feed link that never resolves, while every pipeline run reports success. Hence three rules. Each Source's loaders read every list its entries can live in. Each comic lives in exactly one of the Daily and Political lists, apart from a named handful deliberately shown on both. A derived list, such as the Spanish filter built from the Daily list, is covered by a check rather than read by a loader. A list drifting away from one of its consumers has recurred often enough that these rules are asserted by tests, not left to convention.

### Feed identity
The slug is the feed's identity: one slug means one file at `/feeds/<slug>.xml`, owned by exactly one feed-generating Source. Two Sources claiming the same slug is not a merge — each generator writes the whole file, so whichever runs last wins and the other's content is destroyed. Because the `<guid>` changes with the source, subscribers see each overwrite as new items and receive the same strip repeatedly. This is asserted by the catalog integrity tests rather than left to convention, because the pipeline reports success either way.

A comic's declared `source` is the authority on ownership, and its `url` must name the same host — the two disagreeing is the signature of a catalog entry that was bulk-edited without its url being updated.

### Source slug
The identifier a Source serves a comic under, when that differs from the slug ComicCaster files the feed under (`source_slug` in the catalog, defaulting to `slug`). Needed when two Sources carry genuinely different runs of the same comic: Comics Kingdom and GoComics both publish Edge City, but from different years of its archive, so each run is a distinct work needing its own feed while upstream still knows only one path.

Two Sources carrying the same comic is not automatically two works. Establish which case you are in by comparing the actual strips — identical art means pick one Source and drop the other; genuinely different runs mean give each its own slug. The date printed in the artwork cannot settle it, since it carries no year.

### Reauth
The manual, human-in-the-loop browser login that re-seeds the stored browser session an authenticated Source's scrape depends on. Distinct from an automated token refresh: the operator types the credentials themselves, because the upstream bot check rejects scripted fills, and the resulting session is written into a persistent browser profile that later unattended runs consume.

A reauth counts as successful only if it *persisted* a new session. A browser showing a logged-in page can leave the stored session untouched, so the outcome is confirmed by checking that the stored expiry moved forward — never by how the page looks. Session lifetimes are set by the provider and are read from the stored session rather than assumed, since an interval inferred from past failures can be badly wrong. A stored session may also roll forward on each authenticated use rather than counting from login, and can be revoked by the provider while the stored copy still looks unexpired — so a healthy-looking stored session is a leading indicator, not proof the next unattended run will authenticate.

## Pipeline

### Scrape phase
The network-facing first phase of the daily update: each source is fetched and parsed, writing a dated JSON snapshot per source. The only phase that touches the live comic sites.

### Generate phase
The network-free second phase: each source's generator reads its saved scraped JSON (the newest snapshot, the recent snapshots its Feed window spans, or, for Comics Kingdom, every snapshot ever saved) and writes the feed XML. Safe to re-run during recovery because it never hits the network.

### Invariant guard
The check between the Generate phase and the commit/push phase that asserts every scrape which reported success actually produced usable data, rather than silently shipping a stale feed. Two assertions: the dated JSON snapshot exists, **and** it holds a plausible number of entries for that source (each source sets its own minimum). The count half exists because existence alone was satisfiable by an empty file, which once let a scrape that saved nothing pass as a successful run. The Far Side's New Stuff feed is exempt from the count, because it genuinely publishes almost never.

### Reactive favorites page
The GoComics profile/favorites page the authenticated scraper reads. It classifies each configured comic as updated (a `ComicViewer` container) versus not-issued (a `FeaturesNotIssued` entry) **as of the HTTP request time**, not as of the requested date. A `?date=` param selects which day's strips to show, but a strip only moves into the updated set once it has actually been syndicated. This request-time reactivity is why late-publishing comics are missed at scrape time yet appear on a later fetch of the same date — the root cause behind issues #138 and #164.

### Two-pass scrape
The GoComics-only daily schedule that fetches the Reactive favorites page twice — Pass 1 (~03:20 CT) for overnight-syndicated strips and Pass 2 (~13:00 CT / 14:00 ET) for the mid-morning-Eastern wave — merging both into the same day's JSON. (Times are Central; the automation host runs on US Central time, so logs print CDT/CST.) Introduced for #138. The other sources publish reliably enough on a single pass.

### Rolling backfill
Part of Pass 2: re-scrape the Reactive favorites page for the last N days (`GOCOMICS_BACKFILL_DAYS`, default 3) via `?date=` and merge any newly-appeared slugs into each day's JSON. Because the page reports a past date's *settled* state once strips exist, this recovers cartoonists who published after both same-day passes or on a next-day lag. Each in-window date is re-fetched on every subsequent day, so within-window late settling is self-healing; lateness beyond the window needs a one-off wider backfill. Introduced for #164.

### Failure alert
The GitHub issue a pipeline run opens when a source fails, identified by a `Pipeline-Failure-Key: <slug>` marker in its body rather than by title or label. One issue per source: a repeat failure comments on the existing issue, and the issue closes itself once that source succeeds again. Covers scrape failures, Invariant guard violations, `git push` failures, and the SSH preflight abort — not feed generation or `git fetch`, which stay log-only. Issues are authored by `github-actions[bot]`, because GitHub sends no notification for an issue you author yourself and the host authenticates as the repo owner.

### Covered set
The list of slugs a given run actually examined, passed alongside the failures. A source is only eligible to have its Failure alert auto-closed if it appears in the covered set, so Pass 2 — which scrapes GoComics alone — cannot close a Comics Kingdom issue by omission. Absence from a run's failures means "healthy" only for sources that run examined; for everything else it means "not looked at."

### Heartbeat
The scheduled off-host check that alerts when *no* pipeline run happened, as opposed to a run that failed. It asks whether any pipeline commit has landed on `main` within a staleness window (20h), ignoring human commits so a code push cannot mask a stalled pipeline. It runs on GitHub Actions rather than the automation host, because a check hosted on the machine it monitors dies with it.

## Feed shaping

### Daily Dose
A dating model for sources that have no per-day permalink: the day's strip selection is made upstream by the publisher, and ComicCaster records it dated by fetch date rather than by the strip's own publication date. Used by The Far Side and Mr. Boffo.

A source whose image lives at a single fixed path overwritten in place each day has no retrievable history, so its feed holds only the current strip (a Feed window of one) and relies on fetch-date identity to give each day a distinct entry.

### Feed window
The number of recent days of strips a generated feed includes. Bounded by what the source's archive can actually serve: a source with distinct per-strip URLs supports a multi-day window, while a single-overwritten-image source supports a window of one.

A feed holds its window only if its generator reads every snapshot the window spans. A scrape that saves each strip once writes only that night's new strips, so a generator rebuilding from the newest snapshot alone shrinks every feed to its latest strip, while the pipeline still reports success. The window is measured in strip dates, not in snapshot files, since days with nothing new and outages leave gaps in the files.

A feed with nothing in its window is left as it is rather than emptied: its generator does not write it, so its last items stay published until the comic posts again.

### Strip identity
What makes one strip distinct from another: its own per-strip address where the source has one, or its fetch date where the strip lives at a single address overwritten each day. Never the strip's date on its own, because several strips can share a date, as in a multi-part story posted together.

The identity is the item's `<guid>`, so a published strip's identity must never change; a change reaches subscribers as a re-delivery (see Feed identity). A scraper decides a strip is already recorded, and a generator deduplicates, by this identity, and a strip's images are the ones stored under its own address rather than everything posted that day.

Comics Kingdom fits neither case. Its per-date address names only the night ComicCaster fetched it, because the site serves its newest post for any date, so a strip that stays up for a week is saved under seven addresses. There a strip's identity is its image set, dated and addressed by its first sighting: the earliest saved snapshot that holds it. That makes the saved Comics Kingdom history load-bearing, so it is append-only. Never scrape a past date (the site answers with its newest post, saved under the wrong date), re-run a night's scrape into the data directory after its feed has shipped (send a manual run to another output directory), relabel records after their feed has shipped, or delete old snapshots; each of these can move a strip's first sighting and re-deliver it.

The rule is Comics Kingdom's alone. GoComics records carry the publisher's own date in their address, so the same strip always gets the same identity, and its merges and backfills (Two-pass scrape, Rolling backfill) are safe.
