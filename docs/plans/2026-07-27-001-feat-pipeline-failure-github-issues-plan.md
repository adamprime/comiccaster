---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
product_contract_source: ce-plan-bootstrap
title: "feat: Open GitHub issues when a pipeline scrape fails"
date: 2026-07-27
type: feat
depth: standard
github_issues: []
related_docs:
  - docs/LOCAL_AUTOMATION_README.md
  - scripts/watch_feedback.py
---

# feat: Open GitHub issues when a pipeline scrape fails

## Summary

The twice-daily feed pipeline currently reports failures to two places only: the log
file (`logs/master_update.log`, `logs/pass2_update.log`) and a macOS desktop
notification via `osascript`. Both runs are unattended — Pass 1 at 03:05 and Pass 2 at
13:00 — so a "Basso"-sound notification on the Mac Mini is effectively invisible. A
source can break and stay broken until someone happens to read a log.

This plan adds a **durable, remote alert**: when a content scrape (or the invariant
guard, or the git push, or the SSH preflight) fails, the pipeline opens a GitHub issue
on `adamprime/comiccaster`. Recurrences comment on the existing issue rather than
opening duplicates, and the issue **auto-closes** when that source next succeeds.

---

## Problem Frame

`local_master_update.sh` is deliberately fail-soft: individual step failures do not
abort the run. Every step is an exit-code check that appends a human-readable string
to a bash array:

```bash
if python scripts/scrape_creators.py; then
    echo "✅ ..."
else
    echo "❌ Creators scraping failed"
    FAILURES+=("Creators scraping")
fi
```

At the end (`local_master_update.sh:369-381`) the array's length decides between a
success notification and a failure notification, then the script always `exit 0` so
LaunchD never retries.

That array is the **only** in-memory record of what broke, and it dies with the
process. There is no external signal.

### Why not do this in CI

The obvious alternative — have the host write a failure manifest and let a GitHub
Action open the issue, keeping credentials in CI — has a disqualifying blind spot:
**if the failure is the `git push` itself, the manifest never reaches GitHub.** The
alerts you most need are exactly the ones that approach drops. Detection and alerting
both belong on the host.

### Why this is cheap

`gh` 2.90.0 is already installed at `/opt/homebrew/bin/gh` and authenticated
(account `adamprime`, keyring, scopes include `repo` and `workflow`).
`mini_master_update.sh:17` already puts `/opt/homebrew/bin` on the LaunchAgent's
`PATH`. **No new secret needs to be provisioned.**

### Correction during implementation: the host must not author the issues

The first implementation had the host create issues directly. It worked, and it was
useless: **GitHub sends no notification for an issue you author yourself**, and the
Mini authenticates as the repo owner. Alerts were invisible to the one person meant
to act on them — confirmed by opening a real issue and getting no email, and by an
empty notification inbox.

The host therefore *detects* and *dispatches*; GitHub Actions *creates*, so issues
are authored by `github-actions[bot]` and notify normally. `gh workflow run` is a
direct API call rather than a `git push`, so the push-failure robustness above is
preserved. Full write-up:
`docs/solutions/best-practices/github-self-authored-issues-dont-notify.md`.

---

## Design

### Split: bash detects, Python reports

The host runs **bash 3.2** (no associative arrays), and the repo's testing standard is
pytest with mocked externals. So the state machine lives in Python, where it can be
unit-tested, and bash only collects slugs and shells out.

`scripts/watch_feedback.py` is the precedent to mirror: a `gh(*args)` subprocess
helper, an `ensure_label()` that creates a colored label on demand, and idempotency by
scanning existing issue bodies for a marker line.

### 1. Bash: a machine-readable channel alongside the human one

`FAILURES` stays exactly as-is — it still drives the log summary and the desktop
notification. A parallel `FAILED_KEYS` array carries stable `<source>:<kind>` slugs,
appended **only** at the in-scope sites:

```bash
FAILURES+=("TinyView scraping")     ; FAILED_KEYS+=("tinyview:scrape")
FAILURES+=("$source invariant (…)") ; FAILED_KEYS+=("$slug:invariant")
FAILURES+=("Git push")              ; FAILED_KEYS+=("push:push")
```

Feed-generation and `git fetch` failures are **out of scope** — they stay in
`FAILURES` (log + notification) but do not open issues.

Source slugs: `gocomics`, `comicskingdom`, `tinyview`, `newyorker`, `farside`,
`creators`, `mrboffo`, plus the pseudo-sources `push` and `preflight`.

### 2. Python: `scripts/report_pipeline_failures.py`, run from Actions

The host dispatches:

```bash
gh workflow run pipeline-alert.yml \
    --field run=pass1 --field date="$DATE_STR" \
    --field covered="$ALERT_COVERED" \
    --field failed="gocomics:scrape,tinyview:invariant" || true
```

`.github/workflows/pipeline-alert.yml` then runs the reporter under
`GITHUB_TOKEN`. All dispatch inputs are bound through `env:` rather than
interpolated into the `run:` script, so no input can be parsed as shell.

For each source in `--covered`:

| state | action |
|---|---|
| in `--failed`, no open issue | **open** an issue |
| in `--failed`, open issue exists | **comment** on it |
| not in `--failed`, open issue exists | **comment + close** it (recovered) |
| not in `--failed`, no open issue | nothing |

Idempotency marker in the issue body, mirroring `watch_feedback.py`'s `Source: `:

```
Pipeline-Failure-Key: tinyview
```

Label `pipeline-failure`, created on demand. Title `[pipeline] TinyView scrape failed`.
Body carries date, run, and failure kind — **no run-log excerpt**: this repo is
public and pipeline logs can carry account emails and cookie paths. The operator
reads the real log on the host.

### 3. `--covered` is the safety-critical part

Pass 2 is **GoComics-only**. It must pass `--covered gocomics,push`. Without that
scoping the 13:00 run would auto-close an open Comics Kingdom issue merely because CK
wasn't in its failure list — CK isn't healthy, it simply wasn't examined.

This also buys a good property: a GoComics failure at 03:05 that Pass 2 repairs at
13:00 closes its own issue.

### 4. The SSH preflight gap

Both scripts abort at `local_master_update.sh:58-67` with `exit 0` when SSH auth
fails — *before any scraping runs*. Under a naive design that produces **zero issues**
on the run that failed hardest. This has bitten the project before (the
`github-comiccaster` alias bug, PR #168).

So the preflight abort branch also fires the reporter, with
`--covered preflight --failed preflight:ssh`, before exiting.

### 5. Failure isolation

The reporter call is wrapped so that a `gh` outage can never break the pipeline:

```bash
python scripts/report_pipeline_failures.py ... || true
```

The reporter itself catches `gh` errors per-source, logs them, and continues.

---

## Decisions Taken

- **Host-side, direct** over host-manifest-plus-CI — survives push failures; auth
  already exists on the host.
- **Scope: scrape + invariant + push (+ preflight)** — generation and `git fetch`
  failures remain log-only.
- **Per-source issues with comment-on-recurrence and auto-close** over a daily rollup
  issue — individually triageable and self-clearing.
- **No consecutive-failure threshold.** Known-flaky sources (TinyView lapses; Comics
  Kingdom sessions expiring ~every 10 days) will open issues on first failure. Accepted
  deliberately: the per-run comment trail on a long-running issue is the outage-duration
  record that would otherwise have to be reconstructed from logs.

## Risks

- **Keychain under launchd.** `gh` reads its token from the macOS keyring. LaunchAgents
  run in the Aqua session and the CK scraper already requires an active GUI login, so
  this should work — but it must be *verified* in a launchd context, not assumed.
  Fallback if it fails: a `GH_TOKEN` in `.env`, which the script already exports.
- **Comment volume.** A 10-day CK outage yields ~10 comments on one open issue.
  Accepted (see above).

## Test Plan

`tests/test_report_pipeline_failures.py`, with the `gh` subprocess mocked — no network,
no real issues:

- opens an issue for a failing source with no existing open issue
- comments (does **not** re-open) when an open issue already carries the marker
- comments and closes when a previously-failing source is healthy
- **never touches a source outside `--covered`** (the Pass 2 regression guard)
- creates the `pipeline-failure` label only when absent
- parses `--failed` slugs into source + kind, tolerating empty input
- a `gh` error on one source does not abort the remaining sources

## Rollout

1. Tests, then reporter script, then bash wiring (TDD).
2. `pytest -v` green before commit — `main` auto-deploys.
3. Verify `gh` from a launchd-context invocation.
4. Force a synthetic failure (e.g. a bogus slug) to confirm open → comment → close
   end-to-end, then close the test issue.
