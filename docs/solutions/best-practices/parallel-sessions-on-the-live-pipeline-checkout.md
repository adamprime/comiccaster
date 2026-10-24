---
title: Running parallel Claude sessions when the main checkout is the live pipeline's working copy
date: 2026-10-24
category: best-practices
module: pipeline
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - "More than one Claude session will change ComicCaster at the same time"
  - "An orchestrating session hands work to side sessions that each open their own PR"
  - "A change needs a host action (venv install or uninstall, pip upgrade) after its PR merges"
  - "Two open PRs touch scripts/local_master_update.sh, the AGENTS.md/CLAUDE.md pair, or a generated file"
  - "A side session reports done and you are about to tell the operator"
tags: [parallel-sessions, worktrees, orchestration, pipeline-lock, merge-order, host-venv, verification]
---

# Running parallel Claude sessions when the main checkout is the live pipeline's working copy

## Context

On 2026-10-24 one orchestrating session ran ComicCaster work in parallel with two
side sessions and landed six PRs between 10:41 and 12:32 CDT: #244 (fetch-feed allowlist),
#245 (host venv vulnerability audit), #246 (agent catalog), #247 (certifi),
#248 (Spanish feed language) and #249 (CI tests `constraints.txt`). Nothing
collided, no pipeline run was disturbed, and every merge was green on its own
head commit. That took deliberate rules, because this repo has a hazard most
repos don't: **`/Users/openclaw/projects/comiccaster` is not just a clone, it is
the production pipeline's working copy.**

LaunchAgents run Pass 1 at 03:05, the Far Side morning pass every 30 minutes from
03:30 to 12:00, and Pass 2 at 13:00, all against that checkout:

- A run on `main` syncs with `git reset --hard origin/main`
  (`scripts/local_master_update.sh:159`, `scripts/local_pass2_update.sh:162`),
  so uncommitted edits in the main checkout are discarded without warning. See
  also the gotcha in `docs/solutions/logic-errors/ssh-preflight-tested-wrong-host.md`.
- A run that finds another branch checked out switches back to `main` and files a
  `branch:wrongbranch` alert, or, if it can't switch cleanly, aborts and ships no
  feeds that run (`scripts/local_master_update.sh:135-148`). Before that guard
  existed, the same situation silently stranded a feed commit:
  `docs/solutions/logic-errors/pipeline-silent-failure-on-wrong-branch.md`. The morning pass
  instead runs a safe-sync check and skips its slot if the checkout is dirty or
  off `main` (`scripts/local_farside_morning.sh:174-185`). Either way, a busy
  main checkout costs an alert, a skipped run, or both.
- Every pass serializes on `logs/pipeline.lock` through `/usr/bin/lockf`
  (`scripts/local_master_update.sh:22-23`, `scripts/local_pass2_update.sh:28-29`,
  `scripts/local_farside_morning.sh:56-59`). The lock only exists since #220
  (2026-10-03); before it, nothing stopped two passes overlapping (session
  history). Anything else that changes what a run depends on, such as the venv,
  must take the same lock or it can land mid-run.

Several sessions multiply each of these: more checkouts to confuse, more PRs
touching the same few shared files, and more "done" reports to relay.

## Guidance

**1. Every session that writes gets its own worktree, and the orchestrator does too.**
Side sessions started with their own worktree (`.claude/worktrees/<name>`, which
is gitignored). The orchestrator also did its own fix, and later its update to
another session's PR branch, in worktrees:

```bash
git worktree add -b fix/fetch-feed-allowlist .claude/worktrees/fetch-feed-allowlist origin/main
# updating someone else's PR branch without touching the main checkout:
git worktree add -b orchestrator/agent-catalog-sync .claude/worktrees/agent-catalog-sync origin/feat/agent-catalog
git push origin HEAD:feat/agent-catalog
```

The main checkout stays on `main`, clean, all day. Remove worktrees once their
branches merge (`git worktree remove`, then `git branch -d`). A session can reuse
its worktree for later branches, each cut fresh from `origin/main`.

Run tests from a worktree with the host venv's interpreter and the worktree on
the path. The venv's `comiccaster` is an editable install of the *main
checkout*, so `venv/bin/pytest` and scripts run by path import the main
checkout's copy. `python -m pytest` puts the current directory first, and
`PYTHONPATH=.` makes that explicit (session history; measured 2026-10-24):

```bash
PYTHONPATH=. /Users/openclaw/projects/comiccaster/venv/bin/python -m pytest -q
```

To prove a dependency change, build a throwaway venv from the production base
interpreter (`/opt/homebrew/opt/python@3.14/bin/python3.14`; bare `python3` on
the host is Apple's 3.9.6). Never use the host venv for that.

**2. Split the shared files before anyone commits.** A few files are touched by
most pipeline changes. On 2026-10-24 they were `scripts/local_master_update.sh`, the
`AGENTS.md`/`CLAUDE.md` twins, `docs/LOCAL_AUTOMATION_README.md`,
`constraints.txt`, the `paths-ignore` lists in `.github/workflows/`, and
`docs/STATUS.md`. Leave `STATUS.md` to whichever session closes out the day.

Give each session a named region. On 2026-10-24 the catalog work owned the Phase 2 generator block and the push-recovery regen block of
`local_master_update.sh`, and the audit work owned the preflight block and the
`ALERT_COVERED` line. In `AGENTS.md`, each session anchored its new bullet after
a different existing one. Then check the split held with a trial merge in a
scratch worktree before either PR lands:

```bash
git merge --no-commit --no-ff origin/feat/agent-catalog   # from the other PR's branch
git diff --name-only --diff-filter=U                      # empty = no conflicts
git merge --abort
```

#245 and #246 both edited `local_master_update.sh`, `AGENTS.md` and
`docs/LOCAL_AUTOMATION_README.md`, and merged with no conflicts. For a branch
that isn't checked out anywhere, `git merge-tree --write-tree <a> <b>` answers
the same question without a worktree (session history).

**3. Declare a merge order, and bring later PRs up to date by merging `main` in.**
A PR that merges after another one has to include it, especially when it carries
a **derived file**. #246 committed `public/catalog.json`, which copies each
external comic's `feed_url`. #244 then changed one of those URLs, so the catalog
was stale the moment #244 merged. The fix was to merge `origin/main` into the
#246 branch, rerun `scripts/generate_catalog.py`, and commit the one-line
difference. Merge rather than rebase, so the branch never needs a force-push
while another session might still have it checked out. A committed-data test
(`tests/test_generate_catalog.py`) catches a skipped rebuild.

**4. Host changes happen after the merge, from `main`, under the pipeline lock.**
Venv installs, uninstalls and pip upgrades change what the next run executes, so
they wait for the PR to merge and then run in the main checkout one command at a
time, each under the lock every pass uses:

```bash
cd /Users/openclaw/projects/comiccaster
/usr/bin/lockf -k -t 1800 logs/pipeline.lock git pull --ff-only
/usr/bin/lockf -k -t 1800 logs/pipeline.lock venv/bin/python -m pip install -e . -c constraints.txt
/usr/bin/lockf -k -t 1800 logs/pipeline.lock venv/bin/python -m pip uninstall -y APScheduler tzlocal requests-toolbelt
venv/bin/python -m pip check
```

Checking `launchctl list` for a running pass is not enough: the morning pass fires
every 30 minutes, and a run can start between the check and the install. The
lock makes the change wait instead.

Order matters too: pull and refresh the editable install before uninstalling.
Each pass runs `pip install -e .` before it syncs the checkout
(`scripts/local_master_update.sh:68` vs `:159`), so an unpulled checkout's old
`setup.py` would reinstall the removed packages. See
`docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md`.

Write the `lockf` prefix out in full on every command (or use an array). zsh
does not word-split an unquoted variable, so `L="/usr/bin/lockf -k -t 1800
logs/pipeline.lock"; $L pip ...` fails with exit 127 before anything runs. A
side session hit exactly that on 2026-10-24 (session history), and the
orchestrator hit the same zsh behaviour when it passed a list of branches to
`git push --delete` in one variable.

If the host step is owed after a merge, write it down where the next session
will find it (a memory note or `docs/STATUS.md`) until it is done.

**5. A side session's report is a claim, so verify it before relaying it.**
This is `docs/solutions/best-practices/verify-postconditions-not-success-signals.md` applied to agents. After
each report the orchestrator checked state from the consumer's side: `pip list`,
`pip check` and the audit on the host; `gh pr view --json mergeCommit` and the
CI run for the head SHA; `curl` against the live site. On this day that caught
a side session's own misreading (a CI run it called "pending for about an hour"
was a minute old), and it caught the app's PR panel showing the *previous*
commit's checks as passing (see `docs/solutions/best-practices/github-merge-without-required-checks.md`).

**6. Know how cross-session messages travel.** A message to a session mid-turn
queues until that turn ends. The ownership brief sent after the two sessions
started sat in their queues until each finished its turn. Both read it before
opening their PRs, but nothing guaranteed that. Put file ownership in the
session's starting brief when you can, and check each PR against the rules
either way.

A session that has finished its last turn sends nothing more, so don't count on a
sibling's report to wake you when a CI run finishes. If CI stalls (on #247 the
CodeQL jobs hung at start and ignored cancel), closing and reopening the PR with
a comment starts fresh runs. Meanwhile, build the next branch instead of
polling. If a session proposes a task card for work you then hand to it
directly, dismiss the card so the same fix can't start twice (session history).

**7. Scope changes go to the operator; relay their words exactly.** When a side
session proposed extra work (upgrading the host's pip, changing CI), the
orchestrator verified the claim, asked the operator, and passed the answer on as a
quote. A side session's suggestion is not approval, and an orchestrator's
standing go-ahead (here, "when CI is green, you can merge") covers merging, not
new host changes.

## Why This Matters

Every one of these failures is quiet. Uncommitted edits vanish at the next
reset. A branch left in the main checkout costs an alert, or a run that ships
nothing. A venv change during a run can break that run's imports. Two sessions
adding bullets at the same spot in `AGENTS.md` collide at merge time. A derived
file built before an upstream PR merged ships stale. A merge made on a stale
check panel bypasses the only gate this repo has. None of these shows up in a
single session's tests.

## When to Apply

- Any time two or more sessions, or a session plus the operator, will change the
  repo on the same day.
- Any PR that ends with "and then run X on the host".
- Before relaying any delegated agent's "done" to the operator.

Not needed for a single session doing a docs-only commit, but use a worktree
anyway if the change takes longer than the gap to the next pass.

## Examples

Ownership note sent to the two side sessions on 2026-10-24 (condensed):

> `scripts/local_master_update.sh`: the catalog session hooks into Phase 2
> (~305-315) and the push-recovery block (~544); keep your change to the
> preflight area (~400-430). `AGENTS.md`: put your bullet directly after the
> `check_host_config.py` bullet. Don't touch `functions/` or `public/`.
> Change `venv/` only after your PR merges, under `lockf ... logs/pipeline.lock`.
> Don't switch branches in the main checkout.

The resulting order: #244 merged. #246 merged `main` in and rebuilt
`catalog.json`. #245 merged, then #246. The host venv changed under the lock.
#247, #248 and #249 followed the same pattern.

## Related

- `docs/solutions/logic-errors/pipeline-silent-failure-on-wrong-branch.md`: the runtime guard for a checkout left on a branch.
- `docs/solutions/best-practices/requirements-bumps-dont-reach-the-pipeline-venv.md`: what a host venv change involves.
- `docs/solutions/logic-errors/farside-late-publish-morning-retry-pass.md`: the shared lock and the morning pass schedule.
- `docs/solutions/best-practices/verify-postconditions-not-success-signals.md`: the general rule behind guidance 5.
- `docs/solutions/best-practices/github-merge-without-required-checks.md`: merging when no check is required.
