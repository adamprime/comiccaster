---
title: "fix: Properly center and size comic strips across all RSS feed sources"
type: fix
status: active
date: 2026-04-04
origin: https://github.com/adamprime/comiccaster/issues/106
---

# Fix: Properly Center and Size Comic Strips Across All RSS Feed Sources

## Overview

Issue #106 reports that the centering/sizing fix from #105 isn't working for comics like Zits, Bizarro, Blondie, Carpe Diem, Family Circus, and The Far Side. The #105 fix modified `feed_generator.py` but had two problems: (1) the daily feed pipeline hasn't successfully run since the fix was merged, so no feeds were regenerated with the new code, and (2) the fix itself has issues — a dead `<style>` block in multi-image content and the Far Side feed generator bypasses `feed_generator.py` entirely.

## Problem Frame

A user (dstein766) reports comics are not consistently centered or sized in RSS Guard. The prior #105 fix by ClaudeBot was incomplete:

1. **`<style>` block overriding inline centering**: The feeds HAVE been regenerated (April 3 and 4 runs on a separate always-on machine) and DO contain the inline `max-width: 700px; margin: 10px auto;` fix. But the `<style>` block's `@media (max-width: 600px) { .comic-gallery { margin: 5px 0; } }` rule overrides the centering margin when the RSS reader's pane is narrow, and `.comic-gallery { max-width: 100% }` may also interfere depending on renderer behavior.
2. **Dead `<style>` block**: `_create_multi_image_content` prepends a `<style>` tag to every entry. Most RSS readers strip `<style>` tags entirely (security policy). This is dead weight (~300 bytes per entry across hundreds of feeds) and the `.comic-gallery { max-width: 100% }` rule in the `<style>` block contradicts the inline `max-width: 700px` on the same element.
3. **Far Side bypasses feed_generator.py**: `update_farside_feeds.py` builds its own `<img>` HTML directly, passing it as `description` without `image_url` or `images`. The fix in `feed_generator.py` has zero effect on Far Side feeds.
4. **New Yorker uses single-image path**: Uses `image_url` key, so it goes through `_create_single_image_content` — that path was fixed correctly in #105.

## Requirements Trace

- R1. All comic strips (GoComics, Comics Kingdom, TinyView, Far Side, New Yorker, Creators) must render centered with a consistent max-width of 700px in RSS readers
- R2. Styling must use inline CSS only — no `<style>` blocks (RSS readers strip them)
- R3. Fix must be verifiable by generating a test feed locally before pushing to production
- R4. Existing tests must continue to pass; new tests should verify the fix

## Scope Boundaries

- NOT changing comic scraping logic or data collection
- NOT changing feed metadata (titles, dates, URLs)
- NOT redesigning the multi-image gallery layout — just ensuring consistent centering/sizing
- NOT investigating why the LaunchD daily pipeline hasn't run since April 2 (separate concern)

## Context & Research

### Relevant Code and Patterns

- `comiccaster/feed_generator.py` — `_create_single_image_content` (correctly fixed in #105) and `_create_multi_image_content` (partially fixed, has dead `<style>` block)
- `scripts/update_farside_feeds.py` — Lines 107 and 224 build raw `<img>` HTML, bypassing `feed_generator.py`
- `scripts/generate_comicskingdom_feeds.py` — Uses `images` array → `_create_multi_image_content`
- `scripts/generate_gocomics_feeds.py` — Uses `images` array with single item → `_create_multi_image_content`
- `scripts/generate_tinyview_feeds_from_data.py` — Uses `images` array → `_create_multi_image_content`
- `scripts/generate_creators_feeds.py` — Uses `images` array → `_create_multi_image_content`
- `scripts/update_newyorker_feeds.py` — Uses `image_url` → `_create_single_image_content`

### Key Observation

Both GoComics and Comics Kingdom pass data as `images: [{'url': ..., 'alt': ...}]` arrays, meaning ALL of them go through `_create_multi_image_content`. The "good" feed (The Other Coast/GoComics) and "bad" feed (Zits/Comics Kingdom) both have the OLD HTML without the 700px fix — neither has been regenerated yet. The user's perception that some work and some don't is likely due to differences in source image native widths, not our CSS.

## Key Technical Decisions

- **Inline CSS only**: Remove the `<style>` block from `_create_multi_image_content`. RSS readers (RSS Guard, Thunderbird, Feedly, etc.) strip `<style>` tags. All styling must be inline on the elements themselves.
- **Consistent wrapper pattern**: Both single-image and multi-image paths should use the same centering pattern: `<div style="text-align: center; max-width: 700px; margin: 0 auto;">` as the outermost wrapper.
- **Far Side fix in its own script**: Rather than refactoring Far Side to use `feed_generator.py` (which would be a larger change), apply the same centering wrapper directly in `update_farside_feeds.py` where it builds its HTML. This is the minimal, targeted fix.

## Implementation Units

- [ ] **Unit 1: Fix `_create_multi_image_content` in feed_generator.py**

**Goal:** Remove dead `<style>` block, ensure consistent inline centering/sizing

**Requirements:** R1, R2

**Dependencies:** None

**Files:**
- Modify: `comiccaster/feed_generator.py`
- Test: `tests/test_feed_generator.py`

**Approach:**
- Remove the `responsive_css` variable and the entire `<style>...</style>` block that gets prepended to gallery HTML
- The outer `.comic-gallery` div already has the correct inline styles from the #105 fix (`text-align: center; max-width: 700px; margin: 10px auto;`) — keep those
- Return `gallery_html` directly instead of `responsive_css + gallery_html`

**Patterns to follow:**
- `_create_single_image_content` — the clean pattern with inline-only styles

**Test scenarios:**
- Happy path: Multi-image content has `max-width: 700px` and `margin: 10px auto` on gallery div
- Happy path: Multi-image content does NOT contain a `<style>` tag
- Happy path: Single-image content has centering wrapper (existing test, verify still passes)
- Edge case: Multi-image with 1 image still gets gallery wrapper with centering
- Edge case: Empty images list returns description only

**Verification:**
- `_create_multi_image_content` output contains no `<style>` tags
- Output contains `max-width: 700px` inline on the gallery div

---

- [ ] **Unit 2: Fix Far Side feed HTML in update_farside_feeds.py**

**Goal:** Apply centering wrapper to Far Side feeds that bypass feed_generator.py

**Requirements:** R1

**Dependencies:** None (parallel with Unit 1)

**Files:**
- Modify: `scripts/update_farside_feeds.py`

**Approach:**
- At lines 107 and 224, wrap the existing `<img>` tag in the same centering div pattern: `<div style="text-align: center; max-width: 700px; margin: 0 auto;">...</div>`
- Keep the existing image styles and caption/attribution markup unchanged

**Patterns to follow:**
- `_create_single_image_content` in `feed_generator.py` — same wrapper div pattern

**Test scenarios:**
- Test expectation: none — Far Side script has no existing test file and this is a 2-line styling change. Visual verification via generated feed.

**Verification:**
- Generated Far Side feed XML contains centering div with `max-width: 700px`

---

- [ ] **Unit 3: Update tests for multi-image content**

**Goal:** Ensure test coverage catches the `<style>` block regression

**Requirements:** R4

**Dependencies:** Unit 1

**Files:**
- Modify: `tests/test_feed_generator.py`
- Modify: `tests/test_multi_image_rss.py` (if any assertions break)

**Approach:**
- Update `test_multi_image_centering_wrapper` to explicitly assert NO `<style>` tag is present
- Verify existing multi-image tests still pass after removing `<style>` block
- If any tests in `test_multi_image_rss.py` assert on the `<style>` block presence, update them

**Test scenarios:**
- Happy path: Multi-image HTML contains inline `max-width: 700px` on gallery div
- Regression guard: Multi-image HTML does NOT contain `<style>` tag
- Happy path: All existing feed generator tests continue to pass

**Verification:**
- Full test suite passes (`pytest -v`)

---

- [ ] **Unit 4: Generate test Zits feed locally and verify**

**Goal:** Produce a real feed XML using the fixed code so Adam can preview it in RSS readers

**Requirements:** R3

**Dependencies:** Units 1, 2, 3

**Files:**
- Output: A test Zits feed XML file for manual inspection

**Approach:**
- Write a small script or use existing tooling to generate a single Zits feed from the current scraped data using the fixed `feed_generator.py`
- Output to a temp location for manual review
- Also generate a Far Side feed to verify that fix

**Test scenarios:**
- Test expectation: none — manual visual verification in RSS readers

**Verification:**
- Generated XML contains centering divs with `max-width: 700px`
- Adam verifies appearance in RSS reader/previewer

## System-Wide Impact

- **Interaction graph:** All 5 feed generation scripts produce HTML through `feed_generator.py` (except Far Side which is fixed separately). The fix propagates to all ~650 feeds on next generation run.
- **Error propagation:** No new error paths — this is purely a CSS change in generated HTML.
- **Unchanged invariants:** Feed structure (titles, dates, URLs, enclosures), scraping logic, and deployment pipeline are all unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| RSS readers cache old feed content | User can force-refresh feeds; new entries will have correct styling |
| Removing `<style>` block breaks some reader | The `<style>` block was already being stripped by most readers; inline styles are the correct approach for RSS |
| Daily pipeline hasn't run since April 2 | Separate issue; Adam will run `local_master_update.sh` manually after this fix |

## Sources & References

- Issue #106: https://github.com/adamprime/comiccaster/issues/106
- Issue #105: https://github.com/adamprime/comiccaster/issues/105
- PR #105 fix commit: `e453da4bc`
- Related: Issue #103 (Spanish strip contamination — different problem, user confused the issue numbers)
