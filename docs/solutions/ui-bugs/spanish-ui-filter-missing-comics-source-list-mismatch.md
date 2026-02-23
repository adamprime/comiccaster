---
title: "Creators Spanish comics missing from Spanish UI filter due to catalog desync"
date: 2026-02-23
category: ui-bugs
tags: [creators, spanish-filter, catalog-sync, json, regression]
stack: [javascript, json, python]
---

## Problem

After the Creators expansion, `archie-spanish`, `heathcliff-spanish`, and `wizard-of-id-spanish` existed in `public/comics_list.json` but did not appear in the Spanish UI tab.

## Investigation

- `public/index.html` loads Spanish tab data from `fetch('/spanish_comics_list.json')`.
- Commit `21d6feeb1` added the new Creators comics to `public/comics_list.json`.
- `public/spanish_comics_list.json` did not include those three slugs, so the Spanish filter could not render them.

## Solution

Commit `92d72df48` added the missing entries to `public/spanish_comics_list.json`:

```json
[
  {
    "name": "Archie Spanish",
    "slug": "archie-spanish",
    "url": "https://www.creators.com/read/archie-spanish",
    "source": "creators"
  },
  {
    "name": "Heathcliff Spanish",
    "slug": "heathcliff-spanish",
    "url": "https://www.creators.com/read/heathcliff-spanish",
    "source": "creators"
  },
  {
    "name": "Wizard of Id Spanish",
    "slug": "wizard-of-id-spanish",
    "url": "https://www.creators.com/read/wizard-of-id-spanish",
    "source": "creators"
  }
]
```

## Verification

- Local tests passed: `pytest -v` (171 passed).
- Change was committed and deployed to production (`92d72df48`).
- Production `https://comiccaster.xyz/spanish_comics_list.json` contains all three slugs.

## Key Insight

The Spanish tab depends on a separate derived catalog file. Updating only `comics_list.json` is insufficient for Spanish UI visibility.

## Prevention

- Treat `public/spanish_comics_list.json` as generated output from `public/comics_list.json`.
- Add CI drift check: regenerate Spanish list and fail if diff exists.
- Add a regression test that asserts every Spanish-eligible comic in master catalog appears in Spanish catalog.
- Add a workflow guardrail/checklist: if master catalog changes, regenerate and stage Spanish catalog in same change.

## Related References

- `21d6feeb1` — Added unique active Creators feeds (including these Spanish slugs in master catalog).
- `92d72df48` — Added missing Creators Spanish comics to Spanish filter list.
