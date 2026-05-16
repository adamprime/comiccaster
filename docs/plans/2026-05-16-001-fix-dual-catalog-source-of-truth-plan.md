---
title: "fix: Consolidate dual catalog files to a single source of truth at public/"
type: fix
status: active
date: 2026-05-16
---

# Consolidate dual catalog files to a single source of truth at `public/`

## Overview

The repo has two divergent copies of `comics_list.json` and `political_comics_list.json` that are read by different parts of the pipeline. The GoComics feed generator and a legacy script read stale root-level copies; the UI, Netlify functions, and every other source's scrapers and generators read the current `public/` copies. This silent split means catalog edits to `public/` (the visible source of truth, the file served by Netlify and edited by humans) silently no-op at GoComics feed generation. Two comics added to `public/comics_list.json` in earlier commits today (`the-ancients`, `street-scene`) demonstrate the bug: both scrape successfully, but neither produces a feed because the generator can't see them in its catalog.

Fix is to point `scripts/generate_gocomics_feeds.py` at the `public/` catalogs and delete the stale duplicates. Netlify function copies (`functions/comics_list.json`, `functions/data/comics_list.json`) are auto-synced at deploy time by `netlify.toml`'s build command and don't need attention. Legacy `scripts/update_feeds.py` is out of the active pipeline per STATUS.md and is intentionally left alone.

## Problem Frame

Discovered today while live-testing the new two-pass GoComics scrape. Pass 2 successfully scraped `street-scene` (a comic the user added to favorites this morning) into `data/comics_2026-05-16.json`, but no `public/feeds/street-scene.xml` was generated. Investigation showed `scripts/generate_gocomics_feeds.py:104` reads `Path('comics_list.json')` (a cwd-relative open of the root-level file, last modified March 20, 404 entries — none of today's additions), while `public/comics_list.json` (566 entries, source of truth for the UI) has the new entry. Same pattern at line 112 with `political_comics_list.json` in `scripts/`.

Severity: catalog edits silently fail to produce feeds. Several earlier commits to `public/comics_list.json` (commits `7fe6e2894`, `666946d72`, `e4f1ba741`) are correct for the UI but inert at feed generation. Future contributors editing the obvious file would hit the same wall.

## Requirements Trace

- **R1.** GoComics feed generation reads from the same catalog the UI reads from — no further drift possible.
- **R2.** Today's earlier `public/comics_list.json` additions (`the-ancients`, `street-scene`) start producing feeds on the next scheduled pipeline run.
- **R3.** Daily pipeline continues to produce byte-identical output for comics already in both catalogs (`endtown`, the existing ~400 entries). No regression for existing feeds.
- **R4.** No new sync step, magic, or build-time copying introduced — the fix removes a layer, not adds one.
- **R5.** Future contributors who edit `public/<catalog>.json` see their changes take effect at the next pipeline run without needing to know about a second file.

## Scope Boundaries

- **In scope:** `scripts/generate_gocomics_feeds.py` catalog reads; deletion of the two stale duplicate files; tests that exercise the changed code paths.
- **Out of scope:** Other catalog files (`spanish_comics_list.json`, `tinyview_comics_list.json`, `farside_comics_list.json`, `newyorker_comics_list.json`) — these are single-source already.
- **Out of scope:** The pass-2 scrape implementation itself — that's the in-flight branch this plan sits alongside.
- **Out of scope:** Netlify function bundling — `netlify.toml` already handles `cp public/<file>.json functions/` at deploy time. Verified by reading the build command.

### Deferred to Separate Tasks

- **Legacy `scripts/update_feeds.py` cleanup.** That script's `load_political_comics_list()` (line 728) and direct-open of `comics_list.json` (line 79) point at the same stale paths, but the script is not invoked by `local_master_update.sh` or `mini_master_update.sh` and is documented as replaced. STATUS.md "Last Session" lists modernization work that retired adjacent legacy code; this script is a candidate for deletion in a future maintenance pass.
- **`tests/test_scraper.py` cleanup.** A standalone manual test script (`def main()`, not pytest) that opens `comics_list.json` directly. Out of the test suite, out of CI, low priority. Future cleanup along with `update_feeds.py`.
- **`comiccaster/loader.py` default arg cleanup.** The `Loader` class has `comics_list.json` and `political_comics_list.json` as default function arguments. Callers in the active pipeline don't use these defaults (they pass `public/...` explicitly), so the defaults are harmless. Worth tidying later but not load-bearing.

## Context & Research

### Catalog reader inventory (every reader, every path)

Built by `grep -rn '<filename>'` across `.py`, `.js`, `.html`, `.sh` excluding `node_modules`, `venv`, `.git`.

**Readers of root `./comics_list.json`** (stale, 404 entries, last modified 2026-03-20):
- `scripts/generate_gocomics_feeds.py:104` — `Path('comics_list.json')` — **production daily pipeline, this is the bug**
- `scripts/update_feeds.py:79` — `open('comics_list.json')` — legacy, not in active pipeline
- `tests/test_scraper.py:16` — `open('comics_list.json')` — standalone manual script, not in test suite

**Readers of `./scripts/political_comics_list.json`** (stale duplicate):
- `scripts/generate_gocomics_feeds.py:112` — `Path(__file__).parent / 'political_comics_list.json'` — **production daily pipeline, this is the bug**
- `scripts/update_feeds.py:731` — same pattern — legacy

**Readers of `public/comics_list.json`** (current, 566 entries, source of truth):
- `public/index.html:226`, `public/js/app.js:174` — UI, served by Netlify
- `scripts/comicskingdom_scraper_individual.py:291` — CK scraper
- `scripts/scrape_creators.py:40`, `scripts/generate_creators_feeds.py:32` — Creators source
- `scripts/generate_comicskingdom_feeds.py:156` — CK generator

**Readers of `public/political_comics_list.json`** (current):
- `public/index.html:227` — UI

**Readers of `functions/` and `functions/data/` copies** (Netlify functions, auto-synced at deploy):
- `functions/generate-opml.js:62,66` — bundled by esbuild, copies refreshed by `netlify.toml` build command on every deploy. Stale-in-git is fine; deploy is fresh.

### Relevant code and patterns

- `scripts/generate_comicskingdom_feeds.py:156` — already follows the desired pattern (`Path('public/comics_list.json')`). This is the pattern to mirror in `generate_gocomics_feeds.py`.
- `scripts/generate_creators_feeds.py:5` — comment explicitly references "live `public/comics_list.json` catalog", confirming that `public/` is the intended convention.
- `netlify.toml` build command — explicit `cp public/comics_list.json functions/` step proves Netlify side is already wired to treat `public/` as source.

### Institutional learnings

- `docs/solutions/logic-errors/gocomics-spanish-english-feed-contamination.md` documents prior GoComics scrape-correctness work. The author of that fix updated `scripts/generate_gocomics_feeds.py` (the same file this plan modifies) but didn't notice the catalog-path drift — supporting evidence that the drift has been silent for a long time.
- STATUS.md "Last Session" (2026-05-05) shows recent retirement of legacy code (`comicskingdom_scraper_secure.py`, stale setup docs). This work is in the same spirit — removing duplicate state.

### External references

None — this is a self-contained repo cleanup. No framework docs or external best practices apply.

## Key Technical Decisions

- **Consolidate to `public/<catalog>.json`, don't introduce a sync step.** The other four source generators and all UI readers already use `public/`. Adding a sync step would preserve the duplicate-files smell. Deleting the duplicates and pointing the one remaining stale reader at `public/` is the smaller, cleaner fix.
- **Delete duplicate files in the same commit as the path change.** If we update the generator but leave the files, future contributors could re-introduce the bug by editing the wrong file. Deletion is the durable fix.
- **Don't touch `scripts/update_feeds.py`.** It's a legacy script outside the active pipeline. Touching it expands scope without adding value. Will be cleaned up alongside other legacy retirement in a future maintenance pass (deferred above).
- **Bundle this fix with the pass-2 PR.** Pass 2 surfaced this bug, and pass-2's value for newly-added comics depends on this fix. A single PR tells the coherent story: "two-pass scrape + the catalog-path fix that makes it useful for new additions."
- **No backwards-compat shim.** The two deleted files are not in any external contract — only internal scripts read them, and those are updated atomically in the same commit.

## Open Questions

### Resolved during planning

- **Does Netlify need a build-step update?** No. `netlify.toml`'s build command already does `cp public/X functions/X` on every deploy. The Netlify side is fine.
- **Will deleting the root catalog files break any committed-but-stale-data assumptions?** No. The data files at root were never the source of truth; they were stale-since-March artifacts the generator happened to read. Deleting them removes a footgun.
- **Should we add a test that asserts the generator can't drift again?** Yes — see Unit 4. A test that loads `scripts/generate_gocomics_feeds.py`'s catalog loader and asserts the loaded entries match `public/<catalog>.json` length pins the contract.
- **Should we restore today's pass-2 test artifacts before commits?** Yes — `data/comics_2026-05-16.json` was modified by the live test run, and `public/feeds/*.xml` were regenerated. These belong in the daily pipeline's regular commit flow, not in the code PR. See Unit 5.

### Deferred to implementation

- Whether to delete `./comics_list.json` and `./scripts/political_comics_list.json` via `git rm` or just remove from filesystem. (Same effect via git; will use `git rm` for explicitness in the commit.)
- Whether `tests/test_generate_gocomics_feeds.py` needs any test fixture updates after the path change. Existing tests use `tmp_path / 'comics_list.json'` fixtures, so probably no change needed, but will verify during implementation.

## Implementation Units

- [ ] **Unit 1: Point GoComics generator at `public/` catalogs**

**Goal:** Remove the only readers of the stale root/scripts catalog duplicates from the active pipeline.

**Requirements:** R1, R2, R3, R5

**Dependencies:** None

**Files:**
- Modify: `scripts/generate_gocomics_feeds.py`

**Approach:**
- Change `comics_file = Path('comics_list.json')` (line ~104) to `comics_file = Path('public/comics_list.json')`.
- Change `political_file = Path(__file__).parent / 'political_comics_list.json'` (line ~112) to `political_file = Path('public/political_comics_list.json')`.
- The function still uses cwd-relative resolution (matching how `local_master_update.sh` runs everything from repo root via `cd "$REPO_DIR"`). This mirrors the existing pattern in `scripts/generate_comicskingdom_feeds.py:156` and `scripts/scrape_creators.py:40`.

**Patterns to follow:**
- `scripts/generate_comicskingdom_feeds.py:156` — `comics_file = Path('public/comics_list.json')`. Exact pattern to copy.
- `scripts/generate_creators_feeds.py:32` — `CATALOG_PATH = Path("public/comics_list.json")`. Module-constant variant.

**Test scenarios:**
- Happy path: running `python scripts/generate_gocomics_feeds.py` from repo root with current `public/comics_list.json` (566 entries) and `public/political_comics_list.json` (71 entries) loads the full 637-comic catalog (vs. the pre-fix 467 it loaded from stale copies). Verified by inspecting the generator's INFO log: `Total catalog: <N> comics`.
- Happy path: generator successfully creates `public/feeds/street-scene.xml` and `public/feeds/the-ancients.xml` from scrape data that already exists for those slugs.
- Integration: byte-identical output for comics present in both old and new catalogs (e.g. `chipbok`, `garfield`, `doonesbury`). Compare a few feed XMLs before and after.

**Verification:**
- Generator log shows `Total catalog: 637 comics` (or whatever `len(public_comics) + len(public_political)` is at the time).
- `public/feeds/street-scene.xml` and `public/feeds/the-ancients.xml` exist after a run on data containing those slugs.

- [ ] **Unit 2: Delete the stale duplicate catalog files**

**Goal:** Remove the footgun. After this unit, there is no second copy of either catalog that any script could accidentally read.

**Requirements:** R1, R5

**Dependencies:** Unit 1 (don't delete the files while anything in the active pipeline still reads them)

**Files:**
- Delete: `comics_list.json` (root)
- Delete: `scripts/political_comics_list.json`

**Approach:**
- `git rm comics_list.json scripts/political_comics_list.json` in the same commit that lands Unit 1.
- The legacy `scripts/update_feeds.py` still references these paths but isn't in the active pipeline. If anyone manually runs it, it'll fail loudly with `FileNotFoundError` — preferable to silent stale data. This is acceptable because the script is documented as replaced.

**Patterns to follow:**
- N/A — file deletion.

**Test scenarios:**
- Happy path: after deletion, running `python scripts/generate_gocomics_feeds.py` still succeeds (because Unit 1 changed the paths).
- Error path: running `python scripts/update_feeds.py` now raises `FileNotFoundError` for the missing file. This is intentional. Verified once; documented in the commit message as expected behavior.

**Verification:**
- `find . -maxdepth 2 -name 'comics_list.json' -not -path './public/*' -not -path './functions/*'` returns nothing.
- `find . -maxdepth 2 -name 'political_comics_list.json' -not -path './public/*' -not -path './functions/*'` returns nothing.

- [ ] **Unit 3: Pin the contract with a regression test**

**Goal:** Make it hard for the catalog-path drift to recur. If someone changes the generator's catalog read back to a non-`public/` path, the test fails.

**Requirements:** R1, R5

**Dependencies:** Unit 1

**Files:**
- Modify: `tests/test_generate_gocomics_feeds.py`

**Approach:**
- Add a test class `TestCatalogPath` that asserts the generator's `load_comics_catalog()` reads `public/comics_list.json` and `public/political_comics_list.json`. Strategy: invoke the loader and assert the returned catalog length matches `len(json.load(open('public/comics_list.json'))) + len(json.load(open('public/political_comics_list.json')))`. If a future change re-introduces a stale duplicate, the lengths will diverge and the test fails.
- Alternative considered: pure-string assertion that the source file contains `'public/comics_list.json'`. Rejected — too brittle, doesn't actually exercise the loader.

**Patterns to follow:**
- `tests/test_generate_gocomics_feeds.py` existing test classes — use the same fixture and import pattern.

**Test scenarios:**
- Happy path: `load_comics_catalog()` returns a list whose length equals the sum of entries in `public/comics_list.json` and `public/political_comics_list.json`.
- Edge case: if `public/comics_list.json` is empty or missing, the test should fail cleanly with a descriptive error (this is also a guard against accidental deletion of the source of truth).

**Verification:**
- New test passes on current code.
- Manually verified: reverting Unit 1 makes the new test fail.

- [ ] **Unit 4: Revert today's pass-2 live-test artifacts**

**Goal:** Clean working tree so the feature-branch commits contain only code, not in-flight data updates.

**Requirements:** R3 (no regression for existing feeds), R5

**Dependencies:** Independent of other units; can run any time before commit.

**Files:**
- Restore: `data/comics_2026-05-16.json` (revert to pass-1 state from `/tmp/comics_2026-05-16.pass1.json`, snapshotted earlier in the session)
- Restore: any `public/feeds/*.xml` that were regenerated by today's test run (e.g. `endtown.xml`)

**Approach:**
- `cp /tmp/comics_2026-05-16.pass1.json data/comics_2026-05-16.json` to restore pass-1 state.
- `git checkout public/feeds/` to revert regenerated XML files.
- The pass-2 logic will re-produce these artifacts naturally tomorrow on the next scheduled run, after the launchd plist is installed.

**Test scenarios:**
- Test expectation: none — this is workspace cleanup, no behavioral change.

**Verification:**
- `git status` shows only intentional code changes (no `data/comics_2026-05-16.json` or `public/feeds/*.xml` in the diff).

- [ ] **Unit 5: Validate end-to-end**

**Goal:** Confirm the fix works in the full pipeline without regressing anything.

**Requirements:** R1, R2, R3

**Dependencies:** Units 1, 2, 3

**Files:**
- No file changes — this unit is verification only.

**Approach:**
- Run `pytest -q` — all tests pass (282 existing + Unit 3's new test = 283+).
- Run `python scripts/generate_gocomics_feeds.py` manually against the current `data/comics_2026-05-16.json` (pass-1 state, restored by Unit 4). Confirm log line `Total catalog: 637 comics` (or matching sum) and no errors.
- Spot-check 3 feed files for byte-equality vs pre-fix: pick `garfield.xml`, `doonesbury.xml`, `chipbok.xml`. If these change unexpectedly, something is wrong.
- Confirm `street-scene.xml` and `the-ancients.xml` are NOT generated this run (because pass-1 data on May 16 doesn't have `street-scene`, only pass-2 data did). They'll be generated tomorrow when pass-1 + pass-2 both run normally.

**Test scenarios:**
- Test expectation: none — this is integration verification, covered by Unit 3's test.

**Verification:**
- Full test suite green.
- Generator log shows expanded catalog count.
- Three sample feed files byte-identical to pre-fix state.

## System-Wide Impact

- **Interaction graph:** Only `scripts/generate_gocomics_feeds.py` interacts with the catalogs in the active pipeline. The Netlify functions, UI, and other source scrapers already read from `public/`. No callbacks or middleware involved.
- **Error propagation:** If `public/comics_list.json` ever becomes corrupt or missing, the generator now fails loudly (same as it did before with the stale root copy). No new failure mode introduced.
- **State lifecycle risks:** None. The catalogs are read at generator startup and not mutated.
- **API surface parity:** No external API change. The catalog files served by Netlify (`/comics_list.json`, `/political_comics_list.json`) are unchanged — they were always `public/<file>.json`.
- **Integration coverage:** Unit 3's regression test covers the catalog-loading contract. The byte-equality check in Unit 5 validates that existing feed output is unchanged for comics present in both old and new catalogs.
- **Unchanged invariants:** Feed file naming (`<slug>.xml`), feed XML structure, scrape data file format, all six source scrapers, Netlify deploy contract. This change is purely a "which file does the GoComics generator open" fix.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Pre-existing feeds change unexpectedly because the larger catalog introduces some entry the generator now picks up differently | Spot-check byte-equality on 3 representative feed files in Unit 5; if any byte-changes, investigate before merging. |
| Deleting `./comics_list.json` breaks something I haven't found in the grep audit | Grep was exhaustive across `.py/.js/.html/.sh` excluding `node_modules`/`venv`. Remaining risk is shell scripts not in those extensions or untracked operator scripts. Mitigation: run full test suite + manual generator run before merging. |
| `scripts/update_feeds.py` is unexpectedly invoked by someone after the deletion | Acceptable. Script is documented as replaced. If someone runs it manually they'll get a clear `FileNotFoundError`. |
| Concurrent in-flight pass-2 work conflicts with this fix at merge time | Both changes are on the same feature branch (`feature/pass2-gocomics-scrape` or whatever the user names it). No merge conflict because they touch different lines / different files. |

## Documentation / Operational Notes

- No user-facing docs to update.
- Add a one-line note to the PR description: "This commit removes a long-standing footgun where catalog edits to `public/` silently failed at GoComics feed generation. The fix surfaced while live-testing pass-2 scrape — `street-scene` was the example."
- No rollback runbook needed; the change is small, the test suite covers it, and revert is `git revert` of the commit.

## Sources & References

- **Diagnostic that surfaced the bug:** Live pass-2 test run today (2026-05-16), captured in conversation log.
- **Related code:** `scripts/generate_gocomics_feeds.py:104,112`, `scripts/generate_comicskingdom_feeds.py:156` (pattern reference), `netlify.toml` build command.
- **Related solutions:** `docs/solutions/logic-errors/gocomics-favorites-page-timing.md` (written earlier this session; the pass-2 work that surfaced this bug).
- **Related commits:** `7fe6e2894`, `666946d72`, `e4f1ba741` — catalog cleanup commits whose `the-ancients` and `street-scene` additions are currently inert at feed generation, fixed by this plan.
