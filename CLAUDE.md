# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

ComicCaster's architecture, commands, and the daily feed-update pipeline live in
`AGENTS.md`, imported just below — this file does not restate them. What follows
is *how to work here*: the engineering practices to apply on top of those facts.
(Keep this file and `AGENTS.md` consistent — they're twins: Claude Code / Codex.)

@AGENTS.md

## How we build here

ComicCaster is a real, tested Python + Netlify codebase — not a throwaway script —
so the practices below apply. Right-size them: a typo or one-line fix doesn't need
ceremony; a new comic source or a pipeline change does.

### Test-Driven Development
- Tests are the spec. Write or extend a failing test before the implementation,
  make it pass, then refactor while green.
- Run `pytest -v` before every commit (config in `pytest.ini`; coverage is on by
  default). See Git workflow — `main` ships live, so a green run is the gate.
- Test behavior at boundaries, not internals: scraper input → `data/<src>_$DATE.json`,
  generator JSON → `public/feeds/*.xml`, and feed output shape. `tests/` mirrors source.
- Keep the default run fast and offline. Mock the live comic sources
  (GoComics, Comics Kingdom, TinyView, New Yorker, Far Side, Creators, Mr. Boffo) — never hit
  them in unit tests. Use the existing `network` / `integration` pytest markers for
  the few tests that genuinely need the network.

### SOLID, applied here
- **OCP is already in the codebase.** `scraper_factory.py` selects a scraper by
  source. Add a new comic source by registering a scraper in the factory plus a
  two-phase scrape/generate pair — don't grow an `if/elif` chain.
- A new source = a new scraper (Phase 1: fetch + parse one source, write
  `data/<src>_$DATE.json`) and a new generator (Phase 2: network-free, read the
  latest JSON, write `public/feeds/*.xml`). Mirror the existing pairs exactly.
- Single responsibility: scrapers fetch + parse one source; feed shaping lives in
  `feed_generator.py`. Don't blur the two.

### YAGNI
- Build for the sources and cases that exist today. Don't add config knobs,
  parameters, or abstraction for a hypothetical next source before it's real — the
  factory already makes adding one cheap when the time comes.

## Git workflow
- **Conventional Commits:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`,
  `perf:`, `build:`, `ci:`. The body explains *why*, not what.
- **Stage explicit paths** — `git add <path1> <path2>`. Never `git add -A` or
  `git add .`. The pipeline drops dated JSON into `data/` and regenerates many
  `public/feeds/*.xml`; a blind add sweeps those (and any session-cookie artifacts)
  into a code commit. Commit code changes and feed-data separately.
- **`main` auto-deploys to Netlify** — a push is live for RSS subscribers. So:
  - Run `pytest -v` before you push. A red suite never goes to `main`.
  - Keep code commits small and reversible.
  - For risky code changes, route through a branch + PR so the GitHub Action gates
    it before Netlify ships it. Routine fixes direct to `main` are fine for solo work.
  - The daily pipeline commits and pushes regenerated feed XML to `main` directly —
    that's expected automation (see `AGENTS.md`, Phase 3), not something to "fix."
- `git pull --rebase` before pushing. On a rebase conflict, stop and ask — don't
  try to be clever.
- Never `--no-verify` to skip a hook, never force-push shared `main`, never amend a
  commit that's already been pushed.

## Compound Engineering
The `compound-engineering` plugin is installed on this account, so its skills are
available (`ce-plan`, `ce-work`, `ce-code-review`, `ce-debug`, `ce-compound`, …).
- For non-trivial work (a new source, a pipeline change, anything multi-file):
  plan → work → review → compound. Skip the ceremony for typos and one-liners.
- `docs/` already exists here. Capture tricky fixes under
  `docs/solutions/<category>/<slug>.md` and forward-looking work in `docs/plans/`,
  so the next session — often you, back on this box over Screen Sharing — inherits
  the context instead of rediscovering it.
- `docs/solutions/` is a searchable knowledge store of past solutions (bugs, best
  practices, workflow patterns), organized by category with YAML frontmatter
  (`module`, `tags`, `problem_type`) — relevant to grep when implementing or
  debugging in a documented area.
- `CONCEPTS.md` (repo root) holds the project's shared domain vocabulary — Sources,
  the scrape/generate pipeline, feed-shaping terms — relevant when orienting or
  discussing domain concepts.
- When you solve something non-obvious (a scraper breaking on a site change, a
  Netlify build quirk, a re-auth dance), write the solution doc. That payoff is the
  whole reason to work with this rigor.

## What not to do
- Don't `git add -A` or `git add .` — stage explicit paths (see Git workflow).
- Don't hit live comic sources in unit tests — mock them.
- Don't add a new source with branching logic — register it in `scraper_factory.py`.
- Don't push code to `main` without a green `pytest -v` first — `main` ships live.
- Don't commit secrets or session cookies from the authenticated scrapers
  (Comics Kingdom / TinyView re-auth artifacts). See `SECURITY.md`.
