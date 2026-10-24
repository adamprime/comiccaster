---
title: "\"Merge when CI is green\" is a manual check here: no required checks, auto-merge off, and PR status can lag"
date: 2026-10-24
category: best-practices
module: ci
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - "The operator says to merge a PR once CI is green"
  - "About to merge a PR shortly after pushing to its branch"
  - "Considering GitHub auto-merge, or re-enabling the main-branch ruleset"
  - "A PR shows no Tests run at all"
  - "A CI job is stuck and ignores cancel"
tags: [github, ci, merge, auto-merge, required-checks, ruleset, pr-status, codeql]
---

# "Merge when CI is green" is a manual check here: no required checks, auto-merge off, and PR status can lag

## Context

`CLAUDE.md` tells you to route risky changes "through a branch + PR so the GitHub
Action gates it before Netlify ships it". The Tests workflow does run on PRs
that touch code, but nothing makes a merge wait for it. Checked on 2026-10-24:

- The `main-branch-protection` ruleset (id 4714099) has `enforcement: disabled`.
  Its rules are `deletion`, `non_fast_forward`, `pull_request` and
  `required_status_checks`, so none of them apply.
- `main` has no classic branch protection: `gh api
  repos/adamprime/comiccaster/branches/main/protection` returns 404 "Branch not
  protected".
- Auto-merge is turned off in the repo settings (`allow_auto_merge: false`).

A red PR can be merged, a merge deploys to Netlify straight away, and the only
gate is whoever presses merge. With agents doing the merging ("when CI is green,
you can merge"), that gate is an agent reading check results, and on
2026-10-24 the obvious place to read them was wrong.

## Guidance

**1. Read the checks for the PR's head commit, not a cached summary.** Right
after the orchestrator pushed a catalog rebuild to #246, the Claude desktop app's
PR status (`ccd_pr get_status`) reported "9 passing, 0 pending". Those were the
previous commit's runs. GitHub itself showed Tests still running on the new head.
Before merging, tie every run to the head SHA:

```bash
gh pr view 246 --json headRefOid -q .headRefOid          # the commit being merged
gh run list --branch feat/agent-catalog --limit 4 \
  --json headSha,name,status,conclusion                   # every run must show that headSha
gh pr checks 246 | awk -F'\t' '$2!="pass" && $2!="skipping"'   # anything printed = not ready
```

Merge only when the runs for that SHA have finished and passed:
`gh pr merge N --merge`. This repo uses merge commits, not squash.

The app's panel is not the only signal that can lag. During a GitHub Actions
backlog on 2026-10-19, a PR showed "11/11 checks passing, mergeable" while the
run summary still said in progress, and the session re-checked instead of
merging on one signal (session history). When two signals disagree, wait.

**2. Auto-merge can't stand in for checking, and "merge when green" can't run
unattended.** Auto-merge is off in the settings. On #230 (2026-10-06) the app's
`set_auto_merge` failed with exactly that error (session history). Turning it on
wouldn't help, because GitHub auto-merge waits only for *required* checks, and
nothing is required, so it would merge at once.

Nor can an agent sit and watch. The app wakes a session on CI failures, merge
conflicts and review comments, not when CI passes. Agents in this app are also
told not to poll CI in a loop. In practice, "merge it
once CI is green" means one of two things. Either check once, and if it isn't
done, tell the operator you'll merge on their next message, or on the next event
that wakes you. #235, #238 and #240 merged after the operator's next message.
On #230 a Codecov review comment woke the session first. Or do other real work first and check once
afterwards, which is how #249 went on 2026-10-24.

**3. No checks at all is not green.** Tests and CodeQL skip changes that touch
only `public/feeds/**`, `public/catalog.json`, `data/**`, `docs/**` or `**.md`
(`paths-ignore` in both `.github/workflows/tests.yml` and `codeql.yml`). So a docs-only PR has no Tests
run, and its only gate is the local `pytest -v` that `CLAUDE.md` asks for before
every push. A PR that also touches code does run Tests, because one file outside
the ignore list is enough to trigger it.

**4. A green PR tested its own branch against the `main` of that moment.** When
several PRs merge in a row, each was tested before the others landed. The push
to `main` runs Tests again, but only after Netlify has already deployed the
merge. For a batch, check the combination before the last merge: a trial merge
(`git merge --no-commit --no-ff`, or `git merge-tree --write-tree`), then a
local full suite on the combined tree. On 2026-10-24, combined `main` passed 942
before the last PR of the day went in. A PR whose branch carries a derived file
(such as `public/catalog.json`) must also be rebuilt on top of whatever merged
before it. See
`docs/solutions/best-practices/parallel-sessions-on-the-live-pipeline-checkout.md`.

**5. Stuck runs: close and reopen, don't loop.** On #247 the CodeQL analyses
stalled at start and ignored both cancel and force-cancel, while GitHub's status
page was green. Closing and reopening the PR, with a comment saying why, started
fresh runs on the same commit, and those passed. Don't poll CI in a loop. Check
once, do other work, and check again.

**6. Re-enabling the ruleset is a design decision, not a toggle.** As written,
it would block every merge. It requires a status check named `Tests`, but the
job reports as `test` (the job id in `tests.yml`). Its `pull_request` rule also
demands one approving review, which a solo maintainer can't give to their own
PR. It has no bypass actors, so it would also block the pipeline's direct feed
pushes to `main`. Because of `paths-ignore`, a
required Tests check would never start on feed, data or docs-only changes, and
would leave them waiting forever. Re-enabling needs a bypass for the pipeline's
pushes and a plan for ignored paths: limit the rule to PRs, add an
always-reporting no-op job, or exempt those paths. It's tracked as an open
decision in `docs/STATUS.md`. A required GitHub check still wouldn't catch a
failed Netlify deploy. On 2026-10-07 one went unnoticed behind a green `main`,
and #231 removed the cause.

## Why This Matters

`main` auto-deploys to Netlify, so every merge is a deploy to RSS subscribers.
With nothing enforced, whether CI was green is only known if someone looked at
the right commit. An agent trusting a cached panel, or arming auto-merge, would
ship untested code with every signal saying it was tested.

## When to Apply

- Any merge you make on someone's "merge when green".
- Any merge within a few minutes of a push to the PR branch.
- Before suggesting auto-merge, or changes to the ruleset, for this repo.

## Examples

The #246 timeline on 2026-10-24: the branch was updated by merging `main` in and
rebuilding the catalog, then pushed. Shortly after, the app's status showed 9
passing, 0 pending. `gh run list` showed `CodeQL completed success` and `Tests
in_progress` for the new head. The merge waited for Tests, which passed, and
only then went in.

## Related

- `docs/solutions/best-practices/parallel-sessions-on-the-live-pipeline-checkout.md`: merge order and derived files across several PRs.
- `docs/solutions/best-practices/verify-postconditions-not-success-signals.md`: the panel's "passing" is a success signal, and the head-SHA run is the postcondition.
