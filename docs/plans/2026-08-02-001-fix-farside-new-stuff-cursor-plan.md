---
artifact_contract: ce-unified-plan/v1
artifact_readiness: needs-decision
execution: code
title: "fix: Far Side New Stuff feed is empty and cannot self-recover (cursor regression + unpersisted cursor)"
date: 2026-08-02
type: fix
depth: standard
github_issues: []
related_docs:
  - scripts/scrape_farside.py
  - scripts/local_master_update.sh
  - docs/solutions/logic-errors/power-outage-launchagents-never-load.md
---

# fix: Far Side New Stuff feed is empty and cannot self-recover

## Status

**Confirmed, not yet fixed.** Found incidentally on 2026-08-02 while verifying repo
state after the power-outage catch-up run. Not caused by the outage — pre-existing.

## Summary

`public/feeds/farside-new.xml` currently contains **0 items**, and the code path that
would repopulate it can never trigger. Three independent defects compound:

### 1. The cursor can move backwards

`scripts/scrape_farside.py:166-171`:

```python
cursor_after = max(int(c['id']) for c in archive)
if cursor_after != cursor_before:      # <-- != , not >
    write_cursor(cursor_after)
```

The guard is `!=`, so when the upstream "New Stuff" archive rotates and its max ID
*drops*, the cursor regresses. Observed 2026-08-02: `396 -> 363`.

A regressed cursor is also a **duplicate-emission** risk: if the archive later
includes IDs 364–396 again, every one re-detail's and re-emits as "new".

### 2. The cursor is never persisted

`data/farside_new_last_id.txt` is **tracked** but the pipeline stages only
`data/*.json` and `public/feeds/*.xml` (`scripts/local_master_update.sh:382`, `:447`):

```bash
git add -f data/*.json public/feeds/*.xml     # .txt never matches
```

Each run then begins with `git reset --hard origin/main`, reverting the file to the
last committed value. Confirmed by the snapshots — `cursor_before` is `396` on
**every** run regardless of what the previous run wrote:

```
farside_new_2026-07-31.json  cursor_before 396  cursor_after 396  comics []
farside_new_2026-08-01.json  cursor_before 396  cursor_after 396  comics []
farside_new_2026-08-02.json  cursor_before 396  cursor_after 363  comics []
```

The last real commit to that file was months ago (`3b284d013`).

### 3. Re-seeding can never fire

`scripts/scrape_farside.py:149`:

```python
is_initial = (cursor_before == 0) or (not feed_path.exists())
```

It tests whether the feed file **exists**, not whether it has entries. The feed exists
and is empty, and `cursor_before` is permanently `396`, so `is_initial` is always
`False`.

**Net effect:** cursor pinned at 396 → archive max is now 363 → `to_detail` is always
empty → `comics: []` forever → empty feed, with no path back.

## Why it went unnoticed

The pipeline reports Far Side as ✅ every run. Its invariant check asserts
`farside_new_$DATE.json` **exists** — and it does, containing `"comics": []`. This is
the "verify postconditions, not success signals" trap already documented in
`docs/solutions/best-practices/verify-postconditions-not-success-signals.md`.

## Open decisions (need input before implementing)

1. **Is an empty `farside-new.xml` even a problem?** Upstream may genuinely have
   stopped publishing New Stuff. Check whether thefarside.com still updates that
   section before building recovery machinery for a dead source. *This gates
   everything below — do not skip it.*
2. **Persist the cursor, or derive it?** Either add the `.txt` to the staged paths, or
   drop the file entirely and derive the cursor from the newest ID already present in
   `farside-new.xml` / the latest snapshot. Deriving removes a whole class of
   persistence bug and is likely the better fix — the file exists only because it
   predates the snapshot format.
3. **Backfill or leave the gap?** If the feed should be repopulated, decide whether to
   re-seed with `INITIAL_NEW_STUFF_SEED` most-recent, or accept starting fresh.

## Proposed implementation (pending the decisions above)

1. **Test first** (`tests/test_farside_scraper.py`), per TDD:
   - cursor must never decrease: `cursor_before=396`, archive max `363` → file stays `396`
   - re-seed when the feed has **zero entries**, not merely when it is absent
   - a derived cursor equals the max ID already emitted in the feed
2. Change the guard to `if cursor_after > cursor_before:`.
3. Change `is_initial` to test entry count, not file existence.
4. Whichever of decision 2 is chosen — if keeping the file, add it to both `git add`
   lines; if deriving, delete `LAST_ID_FILE` and its helpers.
5. Verify: `pytest -v` green, then a manual `python scripts/scrape_farside.py` and
   inspect `data/farside_new_$DATE.json` for a non-empty `comics` array.

## Next session — start here

```bash
# 1. Is upstream still publishing? (answers decision 1)
open https://www.thefarside.com/new-stuff

# 2. Current state
cat data/farside_new_$(date +%Y-%m-%d).json
grep -c "<item>" public/feeds/farside-new.xml     # expect 0
git diff data/farside_new_last_id.txt             # expect 396 -> lower, uncommitted
```

Note the working-tree edit to `data/farside_new_last_id.txt` is **expected to vanish**
on the next pipeline run's `git reset --hard`. That is the bug, not a side effect of
investigating it.
