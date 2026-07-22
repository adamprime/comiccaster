---
title: Daily run aborted — SSH preflight tested the wrong GitHub host
date: 2026-07-22
category: logic-errors
module: pipeline
problem_type: bug
component: local_master_update.sh
severity: high
applies_when:
  - "The overnight master update logs 'GitHub SSH authentication failed - check SSH key and keychain' and aborts before scraping"
  - "A day's data/*_$DATE.json files and feed commit are entirely missing (run aborted, not partial failure)"
  - "`ssh -T github-comiccaster` succeeds interactively but the pipeline still reports SSH auth failure"
tags: [ssh, git-remote, host-alias, launchd, preflight, deploy-key, pipeline-abort]
stack: [bash, ssh, git]
github_prs: [168]
---

## TL;DR

`scripts/local_master_update.sh` aborted the entire 2026-07-22 run before Phase 1
because its SSH preflight tested a **hardcoded `ssh -T git@github.com`** (after
`ssh-add ~/.ssh/id_rsa`), but the repo actually pushes over a **dedicated host
alias**: `origin = git@github-comiccaster:adamprime/comiccaster.git`. That alias's
deploy key (`~/.ssh/comiccaster_deploy`) is named via `IdentityFile` +
`IdentitiesOnly yes` in `~/.ssh/config`.

The guard validated the wrong host. It only passed when the agent happened to hold
an `id_rsa` authorized for this repo. Once the agent was empty (nothing loaded it,
or a reboot cleared it), `git@github.com` fell through to defaults → `Permission
denied (publickey)` → `exit 0` abort, **even though the real aliased push
authenticates fine**.

## Why it looked like a keychain problem

The abort message says "check SSH key and keychain", which points at launchd not
reaching the login keychain. That's a real, separate gotcha — but here it was a
red herring. The tell: `ssh -T github-comiccaster` (the alias) succeeds even in a
non-interactive shell with an **empty agent** (`ssh-add -l` → "no identities"),
because the alias authenticates directly from the key file via `IdentityFile`, no
agent required. Only the hardcoded `git@github.com` failed.

## Diagnosis steps

```bash
git remote -v                       # origin uses git@github-comiccaster:...
ssh -T git@github.com               # Permission denied (publickey)  <- what the guard tested
ssh -T github-comiccaster           # successfully authenticated       <- what the push uses
grep -iA6 'host github-comiccaster' ~/.ssh/config   # IdentityFile ~/.ssh/comiccaster_deploy
```

## Fix (PR #168)

Derive the SSH host from the push remote so the guard can never drift from what
the push uses, and drop the stale `id_rsa` agent load:

```bash
REMOTE_URL="$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null)"
SSH_HOST="$(echo "$REMOTE_URL" | sed -n 's/^git@\([^:]*\):.*/\1/p')"
# ... abort if empty ...
if ! ssh -T "$SSH_HOST" 2>&1 | grep -q "successfully authenticated"; then ...
```

Verified: the fixed guard **passes in a non-interactive shell with an empty agent**
— the same class of environment where the old check failed.

## Recovery

Rerun the pipeline manually once SSH is confirmed healthy; it scrapes the current
day and pushes normally:

```bash
bash scripts/local_master_update.sh > logs/manual_recovery_$(date +%Y-%m-%d).log 2>&1
```

7/22 was recovered this way (commit `9c0650f81`, all 8 sources, ALL SUCCESS).

## Gotcha for future manual reruns

The pipeline runs `git reset --hard origin/main` near the top (Phase 0 sync). Any
**uncommitted** working-tree edit — including a fix to this very script — is wiped
by that reset. Commit script changes before relying on them in a run, or expect
the reset to revert them mid-run (bash keeps executing the version it already read
past the guard, but the file on disk reverts).
