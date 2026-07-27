---
title: Duplicate alert issues — label-filtered `gh issue list` is eventually consistent
date: 2026-07-27
category: logic-errors
module: pipeline
problem_type: bug
component: scripts/report_pipeline_failures.py
severity: medium
applies_when:
  - "An idempotent script creates a GitHub issue then re-queries for it moments later and doesn't find it"
  - "Two identical `[pipeline] … failed` issues exist for the same source"
  - "`gh issue list --label X --state open` returns [] for an issue you can see in the web UI"
tags: [github, gh-cli, idempotency, eventual-consistency, alerting, duplicates]
stack: [python, gh-cli]
---

## Problem

`report_pipeline_failures.py` is supposed to open **one** issue per failing source
and comment on it thereafter. During end-to-end testing, two back-to-back runs with
the same failure opened **two** issues (#171 and #172) instead of open-then-comment.

The dedupe lookup was:

```python
gh("issue", "list", "--label", LABEL, "--state", "open", "--limit", "200",
   "--json", "number,body")
```

which returned `[]` — even though the issue had just been created successfully
*with* that label, and was visible via `gh issue list` with no label filter.

## Root cause

**GitHub's label-filtered issue listing is eventually consistent.** For roughly a
minute after an issue is created, it can be absent from a `--label`-filtered query
while already present in an unfiltered one. The reporter therefore concluded "no
open issue exists for this source" and opened a duplicate.

This was not a bug in the marker/dedupe logic — the `Pipeline-Failure-Key:` marker
scan worked correctly. It never got the chance to run, because the *input list* was
empty.

## Fix

Stop depending on the label for lookup. The body marker is already the
authoritative identifier, so query open issues unfiltered and match on the marker:

```python
gh("issue", "list", "--state", "open", "--limit", "200", "--json", "number,body")
```

The `pipeline-failure` label is still applied on creation — it is for humans
filtering the issue tracker, not for machine identity.

Also made duplicate resolution deterministic: if two open issues somehow carry the
same marker, the **oldest** (lowest number) wins, so repeated runs converge on one
issue instead of alternating between them. A subsequent recovery run closes the
stragglers one per run.

## Why it barely mattered in production (and was still worth fixing)

Pass 1 runs at 03:05 and Pass 2 at 13:00 — ten hours apart, far beyond the
consistency window. The duplicate only reproduced because the test fired both runs
within seconds. But the same-run window matters for any future retry or catch-up
path, and the unfiltered query is strictly more robust at no cost.

## Lesson

When building idempotency on top of a remote API, **identify records by data you
control (a marker in the body), and fetch them by the most strongly-consistent
query available.** A server-side filter that is merely convenient can silently
return a stale empty set and turn "check before create" into "create every time."

Unit tests with a mocked `gh` could not have caught this — the mock answered label
queries perfectly. It took a real end-to-end run against GitHub. Keep an
end-to-end verification step for anything whose whole purpose is idempotency.
