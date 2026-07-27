---
title: Alerting via GitHub issues — you get no notification for issues you author
date: 2026-07-27
category: best-practices
module: pipeline
problem_type: best-practice
component: scripts/report_pipeline_failures.py
severity: high
applies_when:
  - "An automated alert opens a GitHub issue but no email or notification ever arrives"
  - "Deciding which identity a bot/automation should authenticate as"
  - "An alert issue is visible in the web UI but absent from the notification inbox"
tags: [github, notifications, alerting, gh-cli, github-actions, automation-identity]
stack: [gh-cli, github-actions]
---

## Problem

The pipeline failure reporter opened GitHub issues correctly from the Mac Mini,
using the `gh` CLI authenticated as `adamprime` — the repo owner. The issues
appeared in the web UI exactly as intended.

**No email ever arrived. No notification was generated at all.**

The whole point of the feature was to catch an overnight failure by morning. It
was inert: the alerts existed, but reached nobody.

## Root cause

**GitHub does not notify you about your own activity.** An issue you author
generates no notification for you — not in the notification inbox, and therefore
not by email. The Mini authenticated as the repo owner, so every alert it created
was, from GitHub's perspective, the owner talking to themselves.

Verified empirically:

```
$ gh issue view 174 --json author --jq '.author.login'
adamprime

$ gh api "/notifications?all=true" --jq '.[] | select(.subject.title | test("TEST"))'
(nothing — no inbox entry at all)
```

Two things this is **not**:

- Not an email-settings problem. No notification was generated, so there was
  nothing for email delivery to deliver.
- Not fixable with a self-`@mention`. Tested directly: an issue body containing
  `@adamprime`, authored by `adamprime`, still produced nothing after 45s. The
  `mention` reason requires a *different* actor to mention you.

The contrast that revealed the fix, from the same notification inbox:

| notification | author | reason | arrives? |
|---|---|---|---|
| pipeline alert issue | `adamprime` (you) | — | **no** |
| `[feedback-site]` issue | `app/github-actions` | subscribed | yes |
| Dependabot PR | `dependabot` | subscribed | yes |

## Fix

**Make the automation act as a different identity.** The alert workflow moved to
GitHub Actions, where `GITHUB_TOKEN` authors issues as `github-actions[bot]`.
Watching the repo then produces a normal `subscribed` notification and an email.

The host still *detects* failures — it just dispatches instead of creating:

```bash
gh workflow run pipeline-alert.yml \
    --field run=pass1 \
    --field covered="$covered" \
    --field failed="$failed" || true
```

This preserves the property that motivated host-side detection in the first
place: `gh workflow run` is a direct API call, **not** a `git push`, so it still
fires when pushing is exactly what is broken.

The alternative — enabling "Include your own updates" at
github.com/settings/notifications — also works, but it is account-wide and emails
you for all of your own activity in every repo. Rejected as too noisy for a fix
that belongs to one automation.

## Related: don't put log tails in public issues

While rerouting, the issue body stopped embedding a 40-line run-log excerpt.
This repo is **public**, and pipeline logs can carry account emails, cookie
paths, and scraper internals. Issues now carry structured facts only (source,
failure kind, run, date); the operator reads the real log on the host.

## Lesson

**An alerting system's deliverable is the notification, not the record.** A
correct, well-tested, idempotent issue that reaches nobody is a failure of the
feature, however green the tests are.

When automation acts on your behalf, ask *who the actor is* — platforms
routinely suppress self-notifications, so automation authenticating as the
person it is meant to alert is a silent dead end. Give the bot its own identity.

And verify delivery end-to-end, with a human confirming receipt. No unit test
and no API assertion would have caught this; it took opening a real issue and
asking "did you get an email?"
