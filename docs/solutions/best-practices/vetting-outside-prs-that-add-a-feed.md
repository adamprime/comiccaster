---
title: Vetting an outside PR that adds a feed — read the author and the feed, not just the diff
date: 2026-11-22
category: best-practices
module: catalog
problem_type: workflow_issue
component: public/external_comics_list.json
severity: low
applies_when:
  - "Someone outside the project opens a PR adding a comic or feed to a list"
  - "A PR's diff is clean but you haven't looked at who sent it or what the feed contains"
  - "Deciding whether to approve CI workflow runs on a first-time contributor's PR"
tags: [pull-requests, contributions, external-rss, promotion, spam, ci-approval, catalog]
github_prs: [266]
---

## TL;DR

The first outside PR, #266, added "Lori Builds Castlori" to
`public/external_comics_list.json`. The diff was perfect: one well-formed entry
plus the regenerated `catalog.json`, with a polite body and a link to a passing
test run in the contributor's fork. It was still a promotion. The account had
opened eight PRs in two weeks adding Castlori, an AI character-chat product, to
awesome-lists. The comic is about building the product. Its feed held five
chapters posted within 30 minutes, each a title plus a link into the product's
reader with no comic content. The PR was closed with a polite decline.
`CONTRIBUTING.md` now says what qualifies, so the next decline can point at a
rule.

## Checklist

1. **Who sent it, and what else are they doing?**
   `gh search prs --author <login>` and
   `gh api users/<login>/events/public` show the account's other PRs and
   activity. A run of near-identical PRs adding the same product to many lists
   is a campaign, not a fan.
2. **What does the feed actually contain?** Fetch it into scratch space as
   untrusted data. Look at the item count, the publish dates (a regular run, or
   a burst?), and whether items carry the comic or only link elsewhere. Read the
   series page too.
3. **Does it meet the rule?** `CONTRIBUTING.md`, "Suggesting an External RSS
   feed": the comic's own feed, an established comic, not advertising, not
   sexually explicit.
4. **Only then, the diff.** For External RSS it should be one list entry plus
   the regenerated `public/catalog.json`. A test requires the catalog rebuild.
   Check the slug isn't taken.

## Don'ts

- **Don't check out or test a fork's code on the pipeline host.** The auto-mode
  classifier blocked exactly that here, and it was right. GitHub holds a
  first-time contributor's workflow runs at `action_required` until a
  maintainer approves them, and approved runs execute in GitHub's sandbox. For
  a JSON-only diff, approving them is safe. Never run the branch locally.
- **Don't post or close without the operator's go-ahead.** A comment from the
  operator's account is public. Draft it and ask first.
- **Don't accuse.** The decline named the criteria the comic missed (an
  established run, items with comic content, not product promotion), not the
  account's behaviour.

## Related

- `CONTRIBUTING.md`, "Suggesting an External RSS feed"
- `docs/solutions/best-practices/catalog-sweep-and-comic-onboarding-by-source.md`
