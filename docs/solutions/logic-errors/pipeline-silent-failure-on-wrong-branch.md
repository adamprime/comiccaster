---
title: Pipeline reported ALL SUCCESS while publishing nothing (wrong branch)
date: 2026-07-28
category: logic-errors
module: pipeline
problem_type: bug
component: scripts/local_master_update.sh
severity: high
applies_when:
  - "A run logs '✅ Successfully pushed' and 'ALL SUCCESS' but feeds on the site are stale"
  - "`git push origin main` prints 'Everything up-to-date' during a pipeline run"
  - "A feed commit exists locally on a branch that is not main"
  - "A local feature branch was silently reset to origin/main"
tags: [git, branch, silent-failure, false-success, push-verification, launchd]
stack: [bash, git]
---

## Problem

On 2026-07-28 the 13:00 Pass 2 run reported:

```
[feat/ck-session-expiry-check 17a2020c5] Pass 2 GoComics feed update for 2026-07-28
 347 files changed, 1399 insertions(+), 1300 deletions(-)
Everything up-to-date
✅ Successfully pushed pass-2 updates
ComicCaster Pass 2 Complete (ALL SUCCESS)
```

Every line is technically true and the conclusion is wrong. **The feed update
never reached subscribers.** No alert fired, because from the script's point of
view nothing failed.

## Root cause

The repo had been left checked out on a feature branch. Both pipeline scripts
assume `main` and never check:

1. `git reset --hard origin/main` — with HEAD on a feature branch, this moves
   *that branch's* pointer to origin/main. Any local commit on it is discarded
   (survives only if already pushed).
2. `git commit` — the feed commit lands on the feature branch.
3. `git push origin main` — pushes the local **`main`** ref, which nobody
   touched. Nothing to send, so git prints "Everything up-to-date" and **exits
   0**. The script reads exit 0 as "published".

The bug is the assumption that `git push` exiting 0 means *your commit* was
published. It only means the named ref had nothing to send.

## Fix

Two independent guards, because either alone leaves a hole.

**1. Branch guard** — refuse to operate on the wrong branch:

```bash
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ "$CURRENT_BRANCH" != "main" ]; then
    if git checkout main; then
        FAILED_KEYS+=("branch:wrongbranch")   # warn, then continue
    else
        report_pipeline_failures "branch" "branch:checkout"
        exit 0                                 # never reset --hard elsewhere
    fi
fi
```

Deliberately *not* `checkout -f`: discarding someone's uncommitted branch work
is worse than skipping a run, so a blocked checkout aborts loudly instead.

**2. Push verification** — prove the commit is actually on the remote:

```bash
verify_push_landed() {
    git fetch -q origin main 2>/dev/null || return 1
    git merge-base --is-ancestor HEAD origin/main 2>/dev/null
}
```

Applied at every push site as `push_with_watchdog && verify_push_landed`. This
is the load-bearing one: it catches *any* cause of "pushed but not published,"
not just the branch case.

Verified against a scratch repo reproducing the exact scenario — commit on a
feature branch, `push origin main` succeeds with nothing to send, and
`verify_push_landed` returns 1 where the old code returned success.

## Recovery, if it already happened

The stranded commit's parent is origin/main, so a fast-forward publishes it
unchanged:

```bash
git checkout main
git merge --ff-only <stranded-sha>
git push origin main
git branch -f <feature-branch> origin/<feature-branch>   # restore from remote
```

## Lesson

**A zero exit code answers the question the command was asked, not the question
you meant.** `git push origin main` was asked "is origin/main up to date with
local main?" — not "did my work get published?" Wherever a step's success is
inferred from an exit code, ask what that code literally asserts, and if the
gap matters, verify the postcondition directly.

This is also the one failure class the alerting system cannot catch by design:
it only reports steps that fail. A step that succeeds at the wrong thing is
invisible to it. The pipeline heartbeat would have caught it eventually — no
pipeline commit on main for 20h — but only after a full day of stale feeds.
Postcondition checks belong next to the steps themselves.
