---
title: A success signal answers the question the operation was asked, not yours
date: 2026-07-28
category: best-practices
module: pipeline
problem_type: best-practice
component: automation
severity: high
applies_when:
  - "Writing automation whose success is inferred from an exit code or a returned status"
  - "A step logs success but the effect you wanted did not happen"
  - "Building anything idempotent on top of a remote API"
  - "Reviewing a fix whose unit tests pass but which has never run end to end"
tags: [postcondition, false-success, silent-failure, exit-codes, idempotency, alerting, testing]
stack: [bash, python, git, gh-cli]
---

# A success signal answers the question the operation was asked, not yours

## Context

Over roughly 24 hours (2026-07-27 to 2026-07-28), while building and then
operating the pipeline's failure-alerting system, **four separate defects turned
out to be the same defect**. Each was found by a different accident. None was
caught by tests. In every one, an operation reported success and **the state that
success implied was not the real state**.

| # | Operation | Reported | Reality |
|---|---|---|---|
| 1 | `gh issue list --label X` | exit 0, empty list | The issue existed; the label index was stale, so dedupe concluded "none open" and opened a **duplicate** |
| 2 | `gh issue create` as the repo owner | exit 0, issue created | The issue was created and **reached nobody** — GitHub sends no notification for your own activity |
| 3 | `git push origin main` | exit 0, "Everything up-to-date" | HEAD was on a feature branch; **nothing was published** |
| 4 | Comics Kingdom reauth | exit 0, success banner, logged-in page | **No usable session survived to the next run.** Whether no token was written, or one was written and server-revoked, is undetermined |

Note the shape is not always "the effect didn't happen." #1 is a *read* — it had
no effect to fail. What it did was answer a question truthfully in a way that made
the caller draw a false conclusion. That is the general case; a missing effect is
one way it shows up.

A fifth instance is worth naming because it is the one engineers most often
trust: the alerting system's **unit tests all passed while the feature was
inert**. The tests asserted that `gh issue create` was invoked with the right
arguments. It was. The issue was created. Nobody was notified. The tests verified
the operation, not the outcome.

Individually each looks like bad luck. Four in a day is a pattern.

## Guidance

**Treat every success signal as the answer to a specific question, and check
whether that question is the one you care about.** They usually differ:

| Signal | The question it actually answers | The question you meant |
|---|---|---|
| `git push` exits 0 | "Did the named ref have anything to send?" | "Did my commit get published?" |
| `gh issue create` exits 0 | "Did the API accept the request?" | "Will a human find out?" |
| Label-filtered list returns `[]` | "Does the index currently show matches?" | "Does such an issue exist?" |
| Reauth script exits 0 | "Did the login flow complete?" | "Is a usable credential on disk?" |
| Mock asserts a call was made | "Did we call the API correctly?" | "Did the effect occur?" |

When the two columns differ and the gap matters, **assert the postcondition
directly** — observe the state you actually want, from the side that will consume
it.

Each fix took a few lines:

```bash
# Not: did push exit 0?  But: is my commit reachable from the remote?
git fetch -q origin main && git merge-base --is-ancestor HEAD origin/main
```

```python
# Not: did the login flow finish?  But: did a new credential land on disk?
expiry_before = read_token_expiry(PROFILE_DIR)
...
driver.quit()             # the write happens on clean shutdown — read after, not before
renewed, message = describe_renewal(
    expiry_before, read_token_expiry(PROFILE_DIR), datetime.now(timezone.utc))
```

```python
# Not: does the label-filtered query find it?  But: does the marker exist at all?
# (label filtering is eventually consistent; the body marker is authoritative)
gh("issue", "list", "--state", "open", "--limit", "200", "--json", "number,body")
```

Three properties make a good postcondition check:

- **Observed from the consumer's side.** The next unattended run reads the cookie
  store, so check the cookie store — not the browser window. Subscribers read
  `origin/main`, so check `origin/main` — not the local ref.
- **Cheap enough to run every time.** All three above are one extra call. A check
  that only runs when someone remembers is not a check.
- **Loud when it fails.** The point is to convert a silent wrong state into a
  failure the existing alerting can see.

## Why This Matters

**This is the one failure class an alerting system cannot catch by design.**
Alerting reports steps that *fail*. A step that succeeds at the wrong thing is
invisible to it — there is no error, no non-zero exit, nothing to report. The
pipeline's own heartbeat would have caught #3 eventually (no pipeline commit on
`main` for 20 hours), but only after the better part of a day of stale feeds.

So postcondition checks are not redundant with monitoring; they cover the gap
monitoring structurally cannot. They belong next to the step, where the failure is
still cheap and the context is still on screen.

The cost asymmetry is stark. Each check is one or two lines. What the missing ones
actually cost: a duplicate issue (during end-to-end testing, not production); an
entire alerting feature that was complete, tested, green — and reached nobody; a
Pass 2 feed update that sat unpublished while the run reported `ALL SUCCESS`; and
one source missing from every feed for a morning.

Be honest about *realized* versus *exposed* cost, though. The unpublished push was
caught within the hour and the missing source within about three, both by
accident rather than by design — someone happened to look. The exposure each
missing check permitted was open-ended; what stopped it was luck. That is the
argument for the check, and inflating the realized numbers to make it would be the
same error this doc is about.

There is also a testing lesson. Mocked tests verify that you called the API the
way you intended. They cannot tell you whether calling it that way achieves
anything, because the mock is built from the same assumption as the code. **For
anything whose entire purpose is an effect — a notification arriving, a commit
publishing, a credential persisting — one real end-to-end exercise is worth more
than a suite of green mocks.** All four defects here were found by running the
thing for real; none by tests.

## When to Apply

Reach for an explicit postcondition check when:

- The step's whole purpose is a side effect elsewhere (publish, notify, persist,
  revoke) rather than a computed return value.
- The operation is a *ref*, *filter*, or *query* that can legitimately succeed
  while matching nothing — `push <ref>`, list-with-filter, conditional update.
- The consumer of the effect is a different process, machine, or human from the
  producer, so nothing else will notice the gap promptly.
- The remote is eventually consistent, so "not found" and "does not exist" are
  different statements.
- A human is meant to be told. Delivery is a postcondition, and it is the one most
  often assumed.

It is not worth the ceremony when the operation's return value *is* the product
(a pure computation), or when a fast, loud downstream failure would surface the
problem anyway.

## Examples

The pipeline's push path, before and after:

```bash
# Before — reported ALL SUCCESS while publishing nothing
if push_with_watchdog; then
    echo "✅ Successfully pushed all updates"
    PUSH_OK=true

# After — success requires the commit to be reachable from origin/main
if push_with_watchdog && verify_push_landed; then
    echo "✅ Successfully pushed all updates"
    PUSH_OK=true
```

Reproduced in a throwaway git repo to prove the check actually discriminates
rather than assuming it. The transcript below is from that one-off session; no
repro script is committed, so re-run it by hand if you need to re-confirm:

```
CASE 1: commit pushed properly
✅ verified on origin/main          exit=0

CASE 2: commit on a feature branch, push main
  (push origin main: nothing to push)
❌ NOT on origin/main               exit=1   <-- old code called this SUCCESS
```

That second case is the whole lesson in four lines: `git push` was truthful, the
exit code was correct, and the conclusion drawn from it was wrong.

## Related

Each of the four incidents has its own doc; this one is the pattern they share.

- [pipeline-silent-failure-on-wrong-branch.md](../logic-errors/pipeline-silent-failure-on-wrong-branch.md) — #3, the push that published nothing
- [github-self-authored-issues-dont-notify.md](github-self-authored-issues-dont-notify.md) — #2, the alerts that reached nobody
- [github-issue-list-label-eventual-consistency.md](../logic-errors/github-issue-list-label-eventual-consistency.md) — #1, the stale query that caused a duplicate
- [comicskingdom-reauth-silent-no-op.md](../logic-errors/comicskingdom-reauth-silent-no-op.md) — #4, the login that persisted nothing
