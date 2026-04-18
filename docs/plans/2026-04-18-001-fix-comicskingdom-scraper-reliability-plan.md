---
title: "fix: Stabilize Comics Kingdom scraper reliability"
type: fix
status: active
date: 2026-04-18
deepened: 2026-04-18
origin: docs/brainstorms/2026-04-18-001-comicskingdom-scraper-reliability.md
---

# fix: Stabilize Comics Kingdom scraper reliability

## Overview

Comics Kingdom is the pipeline's least-reliable source. Current failure pattern (16 events in the 2026-03-27→2026-04-18 log window) is a Chrome renderer timeout at ~29.9s, misreported as "please run reauth script" even when cookies are 1–4 days old. The operator has been running weekly manual reauths that "fix" the symptom without addressing the cause.

The first draft of this plan proposed migrating CK's auth from pickled cookies to a persistent Chrome profile (the pattern TinyView uses successfully). A document-review pass exposed that diagnosis as under-evidenced: the hang shows on `driver.get("https://comicskingdom.com")` *before* any `add_cookie` call, so switching the storage mechanism may not move the hang site. Separately, the review flagged that the `_individual` vs `_secure` split is accidental technical debt, not a principled architecture — `_secure` is imported by the reauth helper and `diagnose_ck_page.py`, so "never in production" is not quite true.

Rather than commit to a fix on a speculative root cause, this plan leads with a cheap diagnostic pass (Unit 1) that produces the data to choose the right fix. Smoke tests (Unit 2) land in parallel as a safety net. Unit 3 is deliberately shaped by Unit 1's findings; three candidate shapes are enumerated with their triggering conditions. Defensive hardening (retry on renderer timeout, popup-dismissal port, entry-count invariant) is deferred to follow-up plans to keep this one focused on the observed fire.

## Problem Frame

The production scraper (`scripts/comicskingdom_scraper_individual.py`) fails roughly once a week on the overnight LaunchD run. The failure fingerprint is consistent across occurrences:

```
📅 Cookie file is [1–4] days old
❌ Error loading cookies: Message: timeout: Timed out receiving message from renderer: 29.xxx
❌ Authentication failed - please run reauth script
```

Observations that reframe this:

- Cookies 1–4 days old are not expired; CK sessions last ~60 days.
- The stack trace shows the 30s renderer timeout on `driver.get("https://comicskingdom.com")` inside `load_cookies()`. The `add_cookie` loop runs *after* this `get`, so the hang is not on cookie injection — it's on the navigation itself.
- Manual reruns always succeed on first cookie load with a fresh Chrome process.
- TinyView (same host, same ChromeDriver, similar anti-bot posture) uses a persistent Chrome profile instead of pickled cookies and shows zero comparable failures in the same window.

These observations are compatible with at least three distinct root causes: (a) the `driver.get + sleep + add_cookie` sequence is the trigger; (b) CK itself serves a slow first navigation when an old session is detected; (c) ChromeDriver renderer-process instability unrelated to session state. The first draft of this plan implicitly assumed (a). The instrumentation pass in Unit 1 will distinguish between them.

Separately, a review of `_individual` vs `_secure` revealed:
- Master script has invoked `_individual` since 2025-11-15 (`d8596247d`).
- `_secure` is imported by `scripts/reauth_comicskingdom.py:14` and `scripts/diagnose_ck_page.py:16` — both are production helpers, so the "`_secure` isn't in production" framing is overstated.
- `_secure` received the 2026-04-09 reliability rewrite (popup dismissal, diagnostic snapshots, lazy-image handling) for CK's favorites-page redesign, which never reached `_individual`.
- `_secure` uses a favorites-page extraction (one page load); `_individual` uses per-URL extraction (153 page loads).
- Neither scraper has any automated test coverage.

Whether the right end state is "keep `_individual`, port helpers from `_secure`," "switch production to `_secure` and deprecate `_individual`," or "merge the two" is itself a decision we do not yet have data to make. Unit 1 collects that data.

## Requirements Trace

- **R1.** Daily pipeline stops reporting "Authentication failed — please run reauth script" for failure modes that are not, in fact, expired auth. (Misdiagnosis is F1 from origin.)
- **R2.** A single transient Chrome/renderer failure during startup no longer forfeits the entire day's CK scrape. (F1)
- **R3.** Silent partial scrapes (e.g., 50/153 entries on a flaky run) are detected and flagged as failures rather than published. (F5) — *Note: this requirement is addressed by a deferred follow-up, not by this plan's units; retained here for traceability.*
- **R4.** A reauth signal is emitted only when the scraper genuinely needs a reauth (cookie expiry in the pickled-cookie world, or profile invalidation in a future profile-based world). Transient Chrome failures produce a distinct signal. (F2)
- **R5.** A minimal safety net of automated tests exists for the CK scraper so future changes don't land blind.
- **R6.** The routine weekly reauth cadence becomes unnecessary — reauth only required on genuine expiry / invalidation. (The primary operator-visible win.)
- **R7.** The `_individual`/`_secure` situation is resolved: either one is authoritative and the other is deleted, or they are merged, based on observed behavior — not speculation.

## Scope Boundaries

- **Not** adding defensive hardening (retry, popup dismissal, entry-count invariant) in this plan. These are legitimate but defend against modes not observed in the current failure log; they belong in follow-up plans once either an incident justifies them or Unit 3's fix lands and exposes them as next priorities.
- **Not** parallelizing the per-URL scrape. Higher-risk, separate analysis needed.
- **Not** moving CK off the Mac Mini, off Selenium, or off the 3 AM overnight schedule.
- **Not** eliminating the ~60-day reauth entirely. Inherent to CK's session lifetime and reCAPTCHA gating.
- **Not** modifying master-script orchestration, Phase 3 push-recovery, or the existing invariant guard from 2026-04-17. Those are working as designed.

### Deferred to Separate Tasks

- **Retry on renderer timeout.** Was former Unit 2. Whether this is still needed depends on Unit 3's shape: if the fix eliminates the renderer-timeout class entirely, retry is vestigial; if the fix coexists with occasional hangs, retry remains worthwhile. Revisit after Unit 3 stabilizes.
- **Popup / interstitial dismissal port.** Was former Unit 3. No popup-caused failures in the current log window; helper exists in `_secure` and may simply land automatically if Unit 3's resolution is "switch to `_secure` in production." Explicit port deferred until a popup-blocked failure is actually observed.
- **Entry-count invariant for CK.** Was former Unit 5. No silent-partial-scrape events observed in the current log window. Defer until an incident justifies it, and then implement as a cross-source generalized guard rather than CK-only.
- **`chmod 700` on TinyView's Chrome profile directory.** Security review surfaced that `~/.tinyview_chrome_profile` is world-readable on macOS (inherits umask 022). Pre-existing issue, not introduced by this plan. Worth fixing but separate from CK work.
- **Delete whichever of `_individual`/`_secure` loses Unit 3's decision.** Follow-up cleanup after Unit 3 is validated for a week of stable overnight runs.
- **Generalize entry-count invariant across all six sources.** If the CK version lands in a future plan.

## Context & Research

### Relevant Code and Patterns

- **Production CK scraper:** `scripts/comicskingdom_scraper_individual.py` (354 lines). Key call sites:
  - `setup_driver` (lines 56–83) — Chrome construction; `show_browser` is an existing parameter (not new), Mini sets it via `CK_SCRAPER_EXTRA_ARGS`.
  - `load_cookies` (lines 95–119) — current hang site. `driver.get("https://comicskingdom.com")` at line 105 is where the 29.x s timeout fires.
  - `is_authenticated` (lines 122–133) — does a live navigation to `/favorites`; also a plausible hang site.
  - `authenticate_with_cookies` (lines 136–161) — where the "please run reauth" message fires unconditionally on any exception.
  - `scrape_comic_page` (lines 178–265) — per-URL extraction. Has layered selector fallbacks at lines 196–206 indicating prior site-markup churn already patched defensively.

- **Reference implementation / production helper dependency:** `scripts/comicskingdom_scraper_secure.py` (655 lines). Imported by:
  - `scripts/reauth_comicskingdom.py:14–18` — imports `setup_driver`, `load_config_from_env`, `authenticate_with_cookie_persistence` from `_secure`.
  - `scripts/diagnose_ck_page.py:16` — imports from `_secure`.

  Helpers living only in `_secure`:
  - `login_with_manual_recaptcha` (line 147) — the interactive login flow; not present on `_individual`.
  - `_save_diagnostic_snapshot` (lines 296–309) — screenshot + HTML dump.
  - Popup dismissal block (lines 321–333) — selector loop for close/dismiss buttons.
  - Lazy-image handling and load-more scroll logic for the favorites page.

- **TinyView profile-auth reference:** `scripts/tinyview_scraper_secure.py:58–80`. The `use_profile=True` branch adds `--user-data-dir=~/.tinyview_chrome_profile` and calls `profile_dir.mkdir(exist_ok=True)`. Used in production by `scripts/tinyview_scraper_local_authenticated.py:160`. Zero auth-related failures in the current log window.

- **Master script wiring:** `scripts/local_master_update.sh:87–96`. Invokes `python scripts/comicskingdom_scraper_individual.py ${CK_SCRAPER_EXTRA_ARGS:-} --date "$DATE_STR" --output-dir data`. No change required by any unit in this plan.

- **Host-specific wrapper:** `scripts/mini_master_update.sh`. Sets `CK_SCRAPER_EXTRA_ARGS="--show-browser"` because unattended headless gets blocked by CK anti-bot.

- **Existing test patterns to follow:**
  - `tests/test_authenticated_scraper.py` — the closest existing analogue (GoComics auth scraper tests). Uses pytest + mocked Selenium driver.
  - `tests/conftest.py` — shared fixtures.
  - `tests/test_tinyview_scraper.py` is further from the shape we need (tests the `comiccaster/tinyview_scraper.py` package module, not a `scripts/` script) — reference only for Selenium-mocking patterns.

- **Diagnostic-snapshot directory convention:** `_secure` writes to `data/ck_diagnostics/`. If Unit 3 ports that helper, the directory needs `.gitignore` coverage and `chmod 700` — flagged but deferred.

### Institutional Learnings

- `docs/internal/COMICSKINGDOM_ANALYSIS.md` documents both extraction strategies and explicitly lists per-URL visits as "Alternative: Visit Individual Comic Pages — If favorites extraction is unreliable." The 2025-11-15 switch to `_individual` was deliberate defense against one specific incident of favorites-page fragility. Not a principled preference for per-URL at the architecture level.
- `docs/internal/RECAPTCHA_SOLUTIONS.md` documents the original pickled-cookie design and its "cookies typically last 30-90 days" expectation. The observed failure mode (stale-but-valid cookies, renderer hang) is not consistent with cookie expiry as the root cause.
- No prior entries in `docs/solutions/` cover CK reliability. Unit 1's findings note will be the first.

### External References

None needed. Pattern comparisons are all in-repo.

## Key Technical Decisions

- **Instrument before fix.** The first draft proposed a profile migration grounded in a plausible but unverified root-cause hypothesis. A 1–2 day instrumentation run is cheap (~50 lines of log-line changes), zero-risk, and produces the evidence to choose the right fix. Worst case: nothing hangs during the observation window and we learn that the failure rate may be lower than assumed.
- **Tests in parallel with observation, not gating.** Unit 2's smoke tests are the safety net for any later invasive change. They don't need to wait for Unit 1's data, and Unit 1 needs no new tests (instrumentation is log-only, no behavior change).
- **Keep Unit 3 shape open.** Three candidate shapes with their triggering conditions are enumerated in Unit 3 below. Committing to the shape now is the same mistake the first draft made.
- **`_individual`/`_secure` question resolves via Unit 1's data.** Whether to keep, switch, or merge is a behavior question — run both under the same conditions, compare. The reauth-helper dependency on `_secure` means we cannot simply delete it without also porting `login_with_manual_recaptcha`, which shapes the cost of each option.
- **No preemptive hardening.** Retry, popup port, and entry-count invariant are genuine good ideas for modes that may eventually bite — but adding them now bundles unexplained complexity into the fix for a specific observed failure. Land one thing at a time.
- **Keep `--show-browser` orthogonal.** Whatever Unit 3 becomes, the visible-browser flag stays controlled by the Mini wrapper. Profile mode (if adopted) and `--show-browser` coexist by design (TinyView proves this).
- **Treat `R4` (distinguishing transient vs genuine reauth) as a property of Unit 3's shape, not a separate implementation concern.** A well-chosen Unit 3 either eliminates the "please run reauth" misdiagnosis (by eliminating the transient mode) or adds the distinguishing log line as part of the fix itself.

## Open Questions

### Resolved During Planning

- **Do we know the root cause of the hang?** No — and the first draft overclaimed. Resolved by adding Unit 1 to gather data rather than commit on speculation.
- **Is `_secure` truly unused?** No. `reauth_comicskingdom.py` and `diagnose_ck_page.py` import from it. Unit 1 accounts for this.
- **Unit sequencing.** Unit 1 first (blocks Unit 3). Unit 2 can run in parallel with Unit 1's observation window. Unit 3 follows Unit 1.

### Deferred to Implementation

- **Unit 3's concrete shape** is deferred by design; Unit 1 produces the data to pick it.
- **Whether retry, popup port, and entry-count invariant eventually get rolled into Unit 3 or stay in follow-up plans** depends on Unit 1's findings and Unit 3's eventual scope.
- **chmod 700 on Chrome profile dir(s)** — TinyView has the same issue; addressed as a cross-cutting security follow-up, not inside any specific unit here.

## Implementation Units

- [ ] **Unit 1: Diagnostic instrumentation and comparison run**

  **Goal:** Produce the evidence needed to choose Unit 3's shape. Answers three questions: (a) where exactly does Chrome hang when the 29.x s timeout fires — domain hit, cookie injection, or auth-check navigation? (b) does `_secure`'s favorites-page flow exhibit the same hang under the same conditions? (c) should `_individual` and `_secure` be merged, one deprecated, or both kept?

  **Requirements:** R1, R4, R7

  **Dependencies:** None.

  **Files:**
  - Modify: `scripts/comicskingdom_scraper_individual.py` (add timestamped log lines; no behavior change)
  - Create: `docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md` (findings note)

  **Approach:**
  - Add a small `_log_timing(label)` helper (module-level) that prints `[<HH:MM:SS.fff>] <label>` to stdout. Use it to bracket every Chrome-interaction boundary in `_individual`:
    - Before and after `driver = webdriver.Chrome(options=options)` in `setup_driver`.
    - Before and after each `driver.get(...)` in `load_cookies` and `is_authenticated`.
    - Before and after the `add_cookie` loop (once before the loop, once after).
    - Before and after `driver.get(url)` inside `scrape_comic_page` for the first 5 comics only (subsequent calls would flood the log; the first 5 characterize the steady state).
  - Keep the existing emoji-style print statements unchanged — the new lines are additive.
  - Behavior change: zero. Only log output shape changes.
  - Observation protocol:
    1. Land the instrumentation; keep the pickled-cookie path intact.
    2. Let the normal LaunchD schedule run for 2–3 nights. That's enough to statistically capture at least one hang event given the observed ~1-in-1.5 failure rate.
    3. If no hang occurs in that window, run the scraper headless (no `--show-browser`) manually at different times of day to try to provoke one. Only proceed to conclusion once at least one hang event has been captured with timestamps, or we've definitively not reproduced in ~5 days.
    4. Separately: run `python scripts/comicskingdom_scraper_secure.py` manually at least twice (different days if possible) with the same instrumentation pattern applied to its `driver.get` calls. Compare timing and failure behavior.
  - Findings note structure:
    - What was captured (timestamps, environment, runs summarized).
    - Which call site(s) hang. Specifically: is the 29s timeout on `load_cookies`'s `driver.get`, `is_authenticated`'s `driver.get`, a `scrape_comic_page` `driver.get`, or somewhere else?
    - Whether `_secure` hangs in the same place, a different place, or not at all.
    - Recommendation: what shape should Unit 3 take? (See Unit 3's enumerated shapes below; the note should pick one or propose another.)
    - Recommendation on the `_individual` vs `_secure` question, with reasoning.

  **Patterns to follow:**
  - Existing `print(f"📅 Cookie file is {cookie_age_days} days old")`-style logging — same stream, same function, no new dependencies.
  - No Python `logging` module introduction (avoid scope creep); `print` with timestamp prefix is sufficient for this pass.

  **Test scenarios:**
  - Test expectation: none — instrumentation adds log output only, no behavior change. Unit 2 provides the safety net for subsequent units that do change behavior.

  **Verification:**
  - Production scraper run produces new `[HH:MM:SS.fff] <label>` lines at every instrumented call site.
  - No functional change: CK scrape still produces `data/comicskingdom_YYYY-MM-DD.json` with 153 entries on a successful run.
  - At least one hang event captured (or ~5 days of no-reproduction documented, whichever comes first).
  - Findings note committed to `docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md` with Unit 3's shape recommendation and the `_individual`/`_secure` recommendation.

- [ ] **Unit 2: Add minimal CK scraper smoke tests**

  **Goal:** Establish a pytest safety net that will fail loudly if Unit 3's changes break basic scraper initialization, cookie loading, or auth flow control. Can run in parallel with Unit 1's observation window.

  **Requirements:** R5

  **Dependencies:** None (can land at any time after Unit 1's instrumentation is in).

  **Files:**
  - Create: `tests/test_comicskingdom_scraper.py`
  - Reference: `scripts/comicskingdom_scraper_individual.py`
  - Reference: `tests/test_authenticated_scraper.py` (closest pattern to follow — also tests a `scripts/` module with mocked Selenium)

  **Approach:**
  - Follow `tests/test_authenticated_scraper.py`'s import pattern for loading a module from `scripts/` in tests (`sys.path` insertion or conftest fixture — match whatever that file does today).
  - Mock `webdriver.Chrome` and driver methods (`get`, `get_cookies`, `add_cookie`, `current_url`, `quit`) rather than launching a real browser.
  - Cover the scraper's control-flow logic, not its network behavior.
  - The `show_browser` parameter already exists in `setup_driver` (it is not new); tests simply exercise both `show_browser=True` and `show_browser=False` to lock in current behavior as Unit 3's baseline.

  **Execution note:** Test-first is appropriate — write each test as a pending assertion against the current code, confirm it passes, then land. A test failing against the current code surfaces a pre-existing bug, not a Unit-2 bug; document it in the PR description rather than fix in this unit.

  **Patterns to follow:**
  - `tests/test_authenticated_scraper.py` import and fixture shape.
  - `tests/conftest.py` for shared pytest fixtures.

  **Test scenarios:**
  - **Happy path:** `load_cookies` loads an existing valid pickle file and returns `True`, having called `driver.get` and `driver.add_cookie`.
  - **Edge case:** `load_cookies` returns `False` (no exception) when the cookie file does not exist.
  - **Error path:** `load_cookies` returns `False` when `pickle.load` raises — and the captured stdout contains a human-readable error, not a traceback. *Note: current code's `except Exception: pass` inside the add_cookie loop silently swallows per-cookie errors; this test is about the outer load, not per-cookie.*
  - **Happy path:** `is_authenticated` returns `True` when mocked `driver.current_url` does not contain `login`.
  - **Error path:** `is_authenticated` returns `False` when `driver.get` raises (matches current `except Exception: return False` behavior).
  - **Integration:** `authenticate_with_cookies` emits the exact "please run reauth" string when `load_cookies` succeeds but `is_authenticated` returns `False`. This test locks the message shape so Unit 3 can intentionally modify it without silently regressing adjacent behavior.
  - **Happy path:** `setup_driver(show_browser=False)` constructs a driver with `--headless=new` in options; `setup_driver(show_browser=True)` does not.
  - **Integration:** Credentials (`COMICSKINGDOM_USERNAME`, `COMICSKINGDOM_PASSWORD`) are read from environment only when `load_config_from_env` is called; capture stdout and assert neither value appears in any printed output.

  **Verification:**
  - `pytest tests/test_comicskingdom_scraper.py -v` all scenarios pass.
  - `pytest -v` overall test count increases by exactly the new tests; no regressions elsewhere.

- [ ] **Unit 3: Apply the fix indicated by Unit 1's findings**

  **Goal:** Make CK scraping reliable by landing the specific change Unit 1's data points to. The shape is deferred until Unit 1 completes — three candidate shapes enumerated below, each with its triggering condition and rough scope. Only one of these (or a hybrid) will be selected.

  **Requirements:** R1, R2, R4, R6, R7 (subset depends on which shape)

  **Dependencies:** Units 1 and 2.

  **Files:** To be determined by Unit 1's findings. Candidate shapes indicate likely files.

  **Approach (conditional on Unit 1 findings):**

  - **Shape A — Profile-based session (original Unit 4 approach).**
    *Trigger:* Unit 1 shows the hang is specifically on `driver.get + add_cookie` sequence, not on plain domain navigation. I.e., `_secure` (or a version of `_individual` that skips the cookie ritual) does not hang in the same conditions.
    *Scope:* Port the TinyView `--user-data-dir` pattern into whichever scraper wins the `_individual`/`_secure` question from Unit 1. Update `reauth_comicskingdom.py` to seed the profile (the rewrite is substantial because `login_with_manual_recaptcha` currently lives in `_secure`; either we keep `_secure` and add profile support there, or we port that function into `_individual`). Add `profile_dir.chmod(0o700)` after creation. Add an explicit empty-profile check that emits a distinct message (not "please run reauth") and bypasses any retry so deploy-day is not confused with a transient failure. Add `data/ck_diagnostics/` to `.gitignore` if the diagnostic-snapshot helper is also ported. Clean up `data/comicskingdom_cookies.pkl` once profile is validated over a week of runs.

  - **Shape B — Consolidate on `_secure` in production, deprecate `_individual`.**
    *Trigger:* Unit 1 shows `_secure` does not hang in the failure conditions that trip `_individual`, and Unit 1's recommendation is that the favorites-page strategy is robust enough given current CK markup. This also inherits `_secure`'s popup dismissal and diagnostic snapshots "for free."
    *Scope:* Update `scripts/local_master_update.sh:91` to invoke `_secure` instead of `_individual`. Verify output JSON schema matches what `scripts/generate_comicskingdom_feeds.py` expects. Run overnight under new invocation; confirm 153/153 on a clean day. After a week of stable runs, delete `scripts/comicskingdom_scraper_individual.py`. Reauth helper and `diagnose_ck_page.py` already import from `_secure`, so no import migration needed.

  - **Shape C — Hang is Chrome/ChromeDriver version instability.**
    *Trigger:* Unit 1 shows the hang is intermittent across both scrapers, both call sites, and correlates with ChromeDriver version rather than any code path. (E.g., the hang only appears after a specific ChromeDriver auto-update.)
    *Scope:* Pin Chrome/ChromeDriver version via `~/bin` install (the Mini already uses `~/bin/chromedriver`; the pin mechanism exists). Add a version check at scraper startup that fails loudly if Chrome and ChromeDriver majors diverge. The profile/pickled-cookie question becomes moot for this cycle.

  - **Hybrid.** Unit 1 may find a combination (e.g., "Shape A on the auth path + Shape C for the underlying Chrome instability"). The implementer picks the shape in the findings note and writes it up before starting, either in this unit's approach or in a revised plan.

  **Execution note:** Whatever shape is chosen, land behavior change in Unit 3 only — do not bundle retry, popup port, or entry-count invariant. Those are deferred and will be evaluated against Unit 3's actual behavior, not against the first draft's speculation.

  **Patterns to follow:**
  - Shape A: `scripts/tinyview_scraper_secure.py:58–80` for `--user-data-dir` adoption. `scripts/tinyview_scraper_local_authenticated.py:160` for the call-site pattern.
  - Shape B: existing master-script invocation pattern at `scripts/local_master_update.sh:87–96`. Reference `scripts/local_master_update.sh:78–84` (GoComics — the other authenticated-scraper call site) for the shape of a clean switch.
  - Shape C: no strong in-repo pattern; document externally in `docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md`.

  **Test scenarios:** Determined by shape. Each shape extends `tests/test_comicskingdom_scraper.py` from Unit 2:
  - **Shape A test scenarios:**
    - *Happy path:* `setup_driver(use_profile=True)` adds `--user-data-dir=~/.comicskingdom_chrome_profile`, creates the directory if missing, and sets mode 0o700.
    - *Integration:* `reauth_comicskingdom.py` mocked-run produces a populated profile directory, does not write a pickle.
    - *Error path:* Empty profile → `authenticate_with_cookies` emits the distinct "profile not seeded, run reauth" message (not "please run reauth") and does not trigger retry.
    - *Integration:* Credentials (`USERNAME`/`PASSWORD`) are not required by the daily scraper when `use_profile=True` — only by `reauth_comicskingdom.py`.
  - **Shape B test scenarios:**
    - *Happy path:* A smoke test of `_secure`'s `extract_comics_from_favorites` against a captured page fixture produces 153 entries matching the `generate_comicskingdom_feeds.py` schema.
    - *Integration:* Running `scripts/comicskingdom_scraper_secure.py --date <YYYY-MM-DD> --output-dir <tmp>` end-to-end (mocked network) writes a JSON file whose shape matches the expected generator input.
  - **Shape C test scenarios:**
    - *Happy path:* Scraper startup validates Chrome major == ChromeDriver major; mismatch causes a clear error message and non-zero exit.

  **Verification:**
  - All tests pass.
  - Overnight run(s) under the chosen shape scrape 153/153 with no "Error loading cookies" / "please run reauth" output, and whichever new distinguishing log line the shape introduces is visible when it should be.
  - Seven consecutive successful overnight runs under the new shape before the follow-up cleanup task to delete the deprecated scraper is initiated.

## System-Wide Impact

- **Interaction graph:** If Unit 3 adopts Shape A and requires an env var (`CK_PROFILE_DIR`) to keep the scraper and reauth helper aligned, that env var becomes a new config surface; document in `.env.example` if added. Shape B avoids this coupling. Shape C is orthogonal.
- **Error propagation:** Unit 1 adds log lines only — no new failure states. Unit 2 adds tests — no runtime impact. Unit 3's failure states depend on shape.
- **State lifecycle risks:** If Shape A is selected, the first post-deploy run requires a reauth; the plan enforces this with an in-code empty-profile check rather than a README note. If Shape B is selected, cookie-file lifecycle is unchanged until the deprecation cleanup. If Shape C, no state-lifecycle change.
- **API surface parity:** Scraper CLI (`--date`, `--output-dir`, `--show-browser`) is preserved across all three shapes. Master script invocation may change in Shape B (filename swap).
- **Integration coverage:** Unit 2's mocked tests do not prove end-to-end Chrome interaction with CK. That's intentional — covered by Unit 3's overnight verification step.
- **Unchanged invariants:** The six-source scrape-and-generate split, the reset-on-start policy, the save/reset/regenerate push-recovery path, and the Phase 2→3 file-existence guard all remain. This plan only touches CK's observed failure path.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Unit 1's observation window is quiet; no hang reproduces. | Run both scrapers manually at varied times of day to try to provoke. If nothing hangs in ~5 days across both, the failure rate may be lower than assumed and Unit 3 can safely be conservative (e.g., instrumentation-plus-retry rather than full migration). |
| Unit 1's findings point to Shape A but the reauth rewrite is larger than the plan anticipates (because `login_with_manual_recaptcha` lives only in `_secure`). | Scope absorbs this: if Shape A is chosen, decide in the findings note whether to keep `_secure` as the auth-flow home (and add profile support there) or to port the login into `_individual`. Either decision is acceptable and will be captured in Unit 3's approach before implementation starts. |
| Shape B is chosen but `_secure` has silent gaps against current CK markup that `_individual`'s layered fallbacks have been papering over. | Unit 1's comparison run surfaces these before Unit 3 commits. The seven-run overnight validation window before deprecating `_individual` is the final safety net. |
| Deferred hardening items (retry, popup port, entry-count invariant) never get picked up because the fire is out. | Acceptable. The whole point of the deferral is that they defend against unobserved modes. If those modes surface in the future, they re-enter the backlog then. |
| Pickled-cookie path continues to deserialize untrusted files during any coexistence window in Shape A. | Cookie file is in a project-writable directory but the Mini is a single-operator machine with no untrusted writers. Document the risk in the Unit 3 PR if Shape A is chosen; consider short coexistence windows. |

## Documentation / Operational Notes

- Unit 1's findings note (`docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md`) is the documentation deliverable for Unit 1 itself. No STATUS.md update is needed until Unit 3 ships.
- Unit 2 needs no doc updates.
- Unit 3, once shaped and landed, should update `docs/STATUS.md` session log with what changed and why, and update `docs/LOCAL_AUTOMATION_README.md` if the operator-facing workflow changes (e.g., Shape A introduces a new reauth flow). Each shape's own approach section should call out which docs it touches.
- The `_individual` vs `_secure` decision, once made, should be captured in a short `docs/decisions/` entry if Shape A or B is chosen, so the choice isn't relitigated in six months.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-18-001-comicskingdom-scraper-reliability.md](../brainstorms/2026-04-18-001-comicskingdom-scraper-reliability.md)
- **Document-review findings (2026-04-18):** Six-persona review pass surfaced the under-evidenced root-cause claim, the `_secure` production-dependency mistake, and the Unit 4/5 scope-creep concerns that drove this revision. Key reviewer outputs retained in session context; summary incorporated into the Problem Frame and Key Technical Decisions.
- **Institutional analysis:** [docs/internal/COMICSKINGDOM_ANALYSIS.md](../internal/COMICSKINGDOM_ANALYSIS.md), [docs/internal/RECAPTCHA_SOLUTIONS.md](../internal/RECAPTCHA_SOLUTIONS.md)
- **Production scraper:** `scripts/comicskingdom_scraper_individual.py`
- **Favorites-page scraper (production helper dependency):** `scripts/comicskingdom_scraper_secure.py`, imported by `scripts/reauth_comicskingdom.py:14–18` and `scripts/diagnose_ck_page.py:16`
- **TinyView profile pattern:** `scripts/tinyview_scraper_secure.py:58–80`, `scripts/tinyview_scraper_local_authenticated.py:160`
- **Master script:** `scripts/local_master_update.sh:87–96`
- **Existing test pattern reference:** `tests/test_authenticated_scraper.py`
- **Current status:** [docs/STATUS.md](../STATUS.md)
- **Failure log window:** `logs/master_update.log` (2026-03-27 → 2026-04-18), 16 `❌ Comics Kingdom scraping failed` events with consistent renderer-timeout fingerprint on the pre-`add_cookie` `driver.get`.
