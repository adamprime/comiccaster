---
title: "fix: Migrate Comics Kingdom auth to persistent Chrome profile"
type: fix
status: active
date: 2026-04-18
origin: docs/plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md
---

# fix: Migrate Comics Kingdom auth to persistent Chrome profile

## Overview

Land Shape A from the Unit 1 diagnosis: replace CK's pickled-cookie startup with a `--user-data-dir` Chrome profile, mirroring the pattern `scripts/tinyview_scraper_secure.py` has been using without incident. This eliminates the `driver.get(comicskingdom.com) + sleep + add_cookie` ritual that the instrumentation captured as the source of the chronic ~20–30s WAF slow-walk. Under a profile, the first request to CK carries session cookies, the WAF treats it as an authenticated visit, and the slow-walk never fires.

Five units: (1) extend `setup_driver` with a `use_profile` flag and profile-directory creation; (2) port `login_with_manual_recaptcha` from `_secure` into `_individual` so reauth can break its dependency on `_secure`; (3) add a profile-aware authentication flow with a distinct empty-profile signal; (4) rewrite `reauth_comicskingdom.py` to seed the profile; (5) flip the daily scrape's default to `use_profile=True` and validate the cutover. `_secure` is not deleted in this plan — that is a separate follow-up after a week of stable runs (explicitly deferred in the parent plan).

## Problem Frame

The parent plan (`docs/plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md`) enumerated three candidate shapes for Unit 3. Unit 1's diagnostic observations (`docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md`) resolved which one is correct:

- `_individual` at 14:09 — success, 153/153, but `driver.get("https://comicskingdom.com")` took **20.4s**.
- `_secure` at 14:24 — **30.0s TIMEOUT** on the exact same call site, reproducing the overnight-failure fingerprint in the middle of the afternoon on a host where cookies were 0 days old.
- Subsequent requests after a session is established (either `/favorites` auth check or per-comic page loads) run at normal speed (~0.5–3s).

The hang is not a property of either scraper's extraction strategy. It's a property of the "navigate to domain, then inject cookies" pattern, because the first request arrives unauthenticated and trips the WAF slow-walk. Shape A sidesteps the pattern entirely: Chrome starts with the profile's cookies already present, so the *first* network request carries a valid session.

TinyView has been running this pattern since introduction with zero comparable failures. The reliability asymmetry between TinyView (profile) and CK (pickled cookies) in the same log window is the architectural asymmetry.

Secondary finding: the per-URL extraction strategy in `_individual` remains the right production scraper. On the same daytime run, `_secure` extracted only 97 of 153 comics (favorites page shows ~98 items even after its built-in "Load more" clicks); `_individual` gets the full 153. The Shape B alternative ("switch master to `_secure`") was eliminated by the diagnosis.

The current `_individual` scraper's coupling to `_secure` is indirect but real: `scripts/reauth_comicskingdom.py:14–18` and `scripts/diagnose_ck_page.py:16` both import from `_secure`. `reauth_comicskingdom.py` specifically imports `login_with_manual_recaptcha` — a 60+ line interactive flow that does not exist on `_individual`. Cutting this dependency is a prerequisite for deleting `_secure` later.

## Requirements Trace

- **R1.** Daily CK scrapes under LaunchD no longer fail due to the WAF slow-walk on the cookie-load domain navigation. (Origin plan's R1, F1.)
- **R2.** `driver.get("https://comicskingdom.com")` is eliminated from the daily scrape's auth path; any first navigation hits an authenticated surface (e.g., `/favorites`) with session cookies already in the request. (Root-cause fix for R1.)
- **R3.** The "please run reauth script" message is emitted only when reauth is actually needed (profile empty, missing, or no longer authenticating). Transient Chrome failures and empty-profile first-boot produce distinct signals. (Origin plan's R4.)
- **R4.** Credentials (`COMICSKINGDOM_USERNAME`, `COMICSKINGDOM_PASSWORD`) are not required by the daily scrape process once the migration is complete — only by the reauth flow that seeds the profile. (Security review finding; Origin S1.)
- **R5.** `~/.comicskingdom_chrome_profile` is created with mode `0o700` so local-user account isolation is respected. (Security review finding; Origin S4.)
- **R6.** The first LaunchD run after deploy emits a clear "profile not seeded" instruction rather than the legacy "please run reauth" string the plan is explicitly trying to disambiguate. (Adversarial review finding; Origin A6.)
- **R7.** `scripts/reauth_comicskingdom.py` stops importing from `_secure`; the login flow lives on the scraper that actually runs in production. After this plan, `_secure`'s only remaining production dependency is `scripts/diagnose_ck_page.py`, which makes `_secure` deletable in a follow-up. (Origin plan's R7.)
- **R8.** Master script, scraper CLI, and Mini wrapper contracts are preserved. `--show-browser` continues to be set by the Mini wrapper for anti-bot reasons; profile mode coexists with it. (Origin constraint.)

## Scope Boundaries

- **Not** deleting `scripts/comicskingdom_scraper_secure.py`. It has one remaining consumer (`scripts/diagnose_ck_page.py`) and must be validated over a week of profile-mode runs before cleanup. Deferred.
- **Not** changing the extraction strategy. Per-URL visits remain, `_individual` remains the production scraper, 153/153 remains the target count. Unit 1 data eliminated Shape B.
- **Not** adding retry-on-renderer-timeout to the auth path. Shape A is expected to eliminate the hang, making retry vestigial; revisit only if profile-mode still exhibits renderer timeouts after a full validation window.
- **Not** porting popup dismissal or diagnostic snapshots from `_secure`. Deferred to a separate hardening plan — current evidence does not show popups blocking `_individual`.
- **Not** adding an entry-count invariant in this plan. Deferred to a cross-source hardening pass.
- **Not** migrating any other source. Shape A is CK-specific; other sources are either already profile-based (TinyView) or have different auth models (GoComics, Creators, Far Side).
- **Not** changing the master script orchestration (`scripts/local_master_update.sh`) beyond whatever falls out of `_individual`'s CLI behavior. Unit 5's cutover changes defaults inside `_individual`, not the master script.
- **Not** changing the 2026-04-17 push-recovery architecture, invariant guard, or six-source structure.

### Deferred to Separate Tasks

- **Delete `scripts/comicskingdom_scraper_secure.py`.** After seven consecutive clean overnight runs under Shape A, and after `scripts/diagnose_ck_page.py` is either updated to not depend on `_secure` or retired. Separate PR.
- **Apply `chmod 700` to `~/.tinyview_chrome_profile`.** TinyView's setup_driver doesn't harden the directory either. Out of scope here (different file, same fix). Separate PR.
- **Remove `data/comicskingdom_cookies.pkl` from the repo.** It's tracked in git (from earlier daily-automation commits). Once profile mode has run cleanly for a week, the pickle file becomes dead data and can be deleted. Separate PR.
- **Update `scripts/diagnose_ck_page.py`** to not depend on `_secure`, or retire it. Only relevant once we're ready to delete `_secure`.
- **Hardening plan: retry, popup port, entry-count invariant.** Revisit after Shape A stabilizes. Only the modes that still surface as failures will make the cut.

## Context & Research

### Relevant Code and Patterns

- **Target scraper (modifying):** `scripts/comicskingdom_scraper_individual.py`. Key symbols:
  - `setup_driver(show_browser=False)` — add `use_profile` parameter.
  - `load_cookies`, `is_authenticated`, `authenticate_with_cookies` — auth flow; the `driver.get(comicskingdom.com) + sleep + add_cookie` pattern in `load_cookies` is what this plan eliminates for the profile path.
  - `load_config_from_env` — currently calls `get_required_env_var` for `USERNAME`/`PASSWORD`; R4 says these must become optional on the daily-scrape path.
  - Instrumentation from PR #114 (`_log_timing`) is already present and valuable for Unit 5's verification — leave it in place through this plan, remove in a follow-up once Shape A has proven itself.

- **Reference implementation (to match):** `scripts/tinyview_scraper_secure.py`. Look at:
  - `setup_driver(show_browser, for_auth, use_profile)` at the top of the file — the exact `--user-data-dir` pattern.
  - `~/.tinyview_chrome_profile` location and `Path.home() / '...'` construction.
  - Caller invocation in `scripts/tinyview_scraper_local_authenticated.py` as `setup_driver(show_browser=False, use_profile=True)`.

- **Source of the login flow (porting from):** `scripts/comicskingdom_scraper_secure.py`. Symbols to port:
  - `login_with_manual_recaptcha(driver, username, password)` — the interactive reCAPTCHA + login flow. Currently the only consumer outside `_secure` is `reauth_comicskingdom.py`.
  - Not `authenticate_with_cookie_persistence` — that function wraps cookie pickling, which is exactly what Shape A is replacing. Reauth calls it today; Unit 3/4 replace that call.

- **Reauth entry point (rewriting):** `scripts/reauth_comicskingdom.py`. Currently imports three symbols from `_secure`; post-plan imports the ported login from `_individual` instead.

- **Diagnostic peer (not modifying):** `scripts/diagnose_ck_page.py`. Still imports from `_secure`. Intentionally untouched in this plan — its migration is the follow-up gating `_secure`'s deletion.

- **Master script (unchanged):** `scripts/local_master_update.sh:87–96`. Continues to invoke `python scripts/comicskingdom_scraper_individual.py ${CK_SCRAPER_EXTRA_ARGS:-} --date "$DATE_STR" --output-dir data`. No changes required — Unit 5 changes the scraper's internal default, not its CLI contract.

- **Host wrapper (unchanged):** `scripts/mini_master_update.sh`. Continues to set `CK_SCRAPER_EXTRA_ARGS="--show-browser"`. Profile mode coexists with visible-browser flag.

- **Existing test scaffolding (extending):** `tests/test_comicskingdom_scraper.py` from PR #114 already has 11 mocked-driver smoke tests. Each Unit in this plan adds to that file; no new test file created.

- **CI:** `.github/workflows/tests.yml` installs dependencies via `pip install -r requirements.txt` (now including `webdriver-manager` after PR #116). No CI changes needed for this plan.

### Institutional Learnings

- `docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md` — the Unit 1 findings note that grounds this plan. Documents the observed timings, the call-site confirmation, the WAF slow-walk hypothesis, and the rationale for Shape A over B/C. Read this before starting any unit.
- `docs/internal/RECAPTCHA_SOLUTIONS.md` — documents the original pickled-cookie design. The premise ("log in once manually, reuse cookies for ~60 days") remains correct; what changes is *how* Chrome holds those cookies between runs. Useful background only.
- `docs/internal/COMICSKINGDOM_ANALYSIS.md` — documents the per-URL vs favorites-page tradeoff. The per-URL path continues to be the right choice for extraction (confirmed by Unit 1 finding that `_secure` only captures 97/153).
- Origin plan — all five document-review persona agents' findings were folded into the origin plan's risks and decisions; this plan inherits those and addresses the ones that are specifically relevant to Shape A (R3–R6 above).

### External References

None used. Pattern is entirely local (TinyView); Chrome `--user-data-dir` behavior is stable and well-known from the TinyView precedent.

## Key Technical Decisions

- **Profile path: `~/.comicskingdom_chrome_profile`.** Mirrors TinyView's convention. Predictable, user-owned, single source of truth. Not configurable via environment variable in this plan — if config drift becomes a problem later, a `CK_PROFILE_DIR` env var is a trivial follow-up.
- **Profile mode: `0o700` at creation time.** Local-user isolation on macOS. Applied inside `setup_driver` immediately after `mkdir`. Same consideration applies to TinyView but is deferred to a separate fix.
- **Port `login_with_manual_recaptcha` into `_individual`, not into a new shared module.** Only two consumers exist (reauth + potential future CK scrapers); a shared `comiccaster/` helper would be speculative abstraction. If a third consumer appears, extract then.
- **`use_profile=True` becomes the default of `setup_driver` in Unit 5.** Earlier units add the flag and make it work; the cutover is an explicit default flip so the behavior change is visible in one reviewable diff. Backward-compat mode (`use_profile=False`) remains available via CLI flag for debugging or for comparing against pre-migration behavior.
- **Pickled-cookie code path remains present but unreached on the default path.** `load_cookies`/`save_cookies` stay in the file; `authenticate_with_cookies` branches on `use_profile` and skips the pickle path entirely when `True`. This keeps Unit 5's diff small (a default change, not a code removal) and leaves a trivial rollback in case Shape A surprises us. Cleanup of the dead pickle path is a follow-up.
- **Empty-profile detection emits a new message: `"⚠️  Chrome profile at <path> has no stored session. Run scripts/reauth_comicskingdom.py to seed it."`** This is distinct from `"❌ Authentication failed - please run reauth script"` so operators (and future log-watchers) can differentiate "never seeded" from "session expired" from "transient Chrome failure."
- **Credentials become optional on the daily-scrape path (R4).** `load_config_from_env` gains a flag or a split: when the caller is the daily scraper with `use_profile=True`, missing credentials are acceptable. When the caller is `reauth_comicskingdom.py`, credentials are still required. The split is handled by adding a `require_credentials` parameter to `load_config_from_env`.
- **Test coverage extends the PR #114 safety net.** Every unit adds scenarios to `tests/test_comicskingdom_scraper.py` rather than creating parallel test files. Characterization-style for Unit 1's flag addition; behavior-testing for Units 2–5.
- **Unit 5 cutover validation is a manual end-to-end run plus one overnight cycle, not a test suite gate.** The integration behavior (Chrome + profile + CK WAF) cannot be mocked meaningfully; the smoke tests assert control flow, and the real verification is a LaunchD-equivalent run on the Mini that scrapes 153/153 without emitting `driver.get(comicskingdom.com)` START/END timing markers (because that code path is no longer invoked).

## Open Questions

### Resolved During Planning

- **Where does `login_with_manual_recaptcha` live post-migration?** In `_individual`. Shared module is premature.
- **What happens to the pickled-cookie code path in `_individual`?** Retained but unreached when `use_profile=True`. Clean up in a follow-up.
- **What happens to `data/comicskingdom_cookies.pkl` on disk?** Left in place. Becomes dead data once Shape A validates. Removal is deferred.
- **How does `_secure` lose its dependency on `reauth_comicskingdom.py`?** Unit 4 rewrites reauth to import from `_individual`. `_secure` then has one remaining dependency (`diagnose_ck_page.py`), which is the gating factor for `_secure`'s deletion in a follow-up.
- **Can `--show-browser` and `--user-data-dir` coexist?** Yes — TinyView proves it. Mini wrapper's `CK_SCRAPER_EXTRA_ARGS="--show-browser"` stays untouched.
- **What's the rollback if Shape A fails?** Revert Unit 5's one-line default flip (`use_profile=True` → `use_profile=False`). The pickled-cookie code path is intact and tested; the scraper would resume the pre-plan behavior on the next run.

### Deferred to Implementation

- **Exact Chrome options flag precedence** for `--user-data-dir` combined with `--headless=new` and the anti-bot detection flags. The Mini always runs with `--show-browser`, so headless+profile is not a production path — but Unit 1's smoke tests will exercise it. If a precedence issue surfaces during Unit 5's validation, resolve in Unit 5's PR. Note that `chrome=147.0.7727.101` (the version in today's runs) has known interactions between `--user-data-dir` and `--headless=new`; if this surfaces, force `use_profile=True` to imply `show_browser=True`.
- **Whether `reauth_comicskingdom.py`'s user prompts need updating** beyond just swapping the cookie-save for a profile-seed. The new message about where the profile lives should be tuned during Unit 4 implementation; the plan specifies the *what* but not the exact prose.
- **Whether to add a one-time migration pre-check** that detects an empty profile AND a present `data/comicskingdom_cookies.pkl` (i.e., fresh Shape A deploy on a host with old pickled cookies), and emits a clearer "you've just deployed Shape A, run reauth" message. This would help the first-deploy experience but may not be worth the conditional complexity. Decide during Unit 3 implementation.

## Implementation Units

- [ ] **Unit 1: Extend `setup_driver` with `use_profile` support**

  **Goal:** Add the `use_profile` parameter to `setup_driver` in `_individual`. When `True`, create (if missing) `~/.comicskingdom_chrome_profile` with mode `0o700` and add `--user-data-dir=<path>` to Chrome options. When `False` (default for this unit), behavior is identical to today — the new code path is not yet reachable from production.

  **Requirements:** R5 (chmod), enabling-piece for R1/R2 via later units.

  **Dependencies:** None.

  **Files:**
  - Modify: `scripts/comicskingdom_scraper_individual.py`
  - Modify: `tests/test_comicskingdom_scraper.py`

  **Approach:**
  - Extend `setup_driver(show_browser=False)` to `setup_driver(show_browser=False, use_profile=False)`. Default remains `False` so nothing changes in production for this unit.
  - When `use_profile=True`: construct profile path as `Path.home() / '.comicskingdom_chrome_profile'`, call `profile_dir.mkdir(parents=True, exist_ok=True)`, then `profile_dir.chmod(0o700)` (idempotent), then add `f'--user-data-dir={profile_dir}'` to Chrome options before the existing flags.
  - All other `setup_driver` behavior — timeouts, anti-bot flags, CDP overrides — unchanged.
  - Import pattern: follow TinyView's `Path.home() / '.tinyview_chrome_profile'` directly; no new config layer.

  **Patterns to follow:**
  - `scripts/tinyview_scraper_secure.py` — `use_profile` handling in its `setup_driver`. Copy the option-add shape; add the `chmod` that TinyView lacks (per the Origin security-review finding).

  **Test scenarios:**
  - **Happy path:** `setup_driver(use_profile=False)` constructs Chrome exactly as today — no `--user-data-dir` argument in options. (Locks backward compatibility.)
  - **Happy path:** `setup_driver(use_profile=True)` adds a `--user-data-dir=` option pointing at the expanded `~/.comicskingdom_chrome_profile` path.
  - **Happy path:** Profile directory is created by `setup_driver(use_profile=True)` when it does not exist.
  - **Edge case:** When the profile directory already exists with content, `setup_driver(use_profile=True)` does not error and does not modify existing contents. Existing files inside the profile are preserved.
  - **Edge case:** Profile directory mode is `0o700` after call, whether it was just created or already existed with a different mode. (Uses `stat.S_IMODE` to check the low bits; tolerates macOS's extra flags on the high bits.)
  - **Integration:** Calling `setup_driver(use_profile=True, show_browser=True)` adds both the `--user-data-dir` and absence of `--headless=new`, with no conflict.

  **Verification:**
  - `pytest tests/test_comicskingdom_scraper.py -v` all scenarios pass, 11 prior + new scenarios.
  - Full suite still at 254 with no regressions (+whatever this unit adds).

- [ ] **Unit 2: Port `login_with_manual_recaptcha` from `_secure` into `_individual`**

  **Goal:** Bring the interactive login flow (user solves reCAPTCHA in a visible browser, script detects redirect away from `/login`) into `_individual`. This decouples `reauth_comicskingdom.py` from `_secure` once Unit 4 consumes it.

  **Requirements:** R7 (enables deleting `_secure` in the follow-up).

  **Dependencies:** None (can run in parallel with Unit 1).

  **Files:**
  - Modify: `scripts/comicskingdom_scraper_individual.py`
  - Modify: `tests/test_comicskingdom_scraper.py`

  **Approach:**
  - Copy `login_with_manual_recaptcha(driver, username, password)` verbatim from `scripts/comicskingdom_scraper_secure.py:147` into `_individual`. Same signature, same behavior, same user-facing prompts.
  - Copy the Selenium `By`, `WebDriverWait`, `EC` imports that the login function needs. Check current imports in `_individual` first; some are already present (`By`, `WebDriverWait`, `EC` are at the top of `_individual`). Add whatever's missing.
  - Do not yet call the ported function from anywhere in `_individual`'s existing code — it exists for Unit 4 (reauth) to consume.
  - `_secure`'s copy of `login_with_manual_recaptcha` remains in place. Do not delete. It will be removed when `_secure` itself is deleted in the follow-up.

  **Execution note:** Characterization test the port. Add a test that asserts the ported function has the same external contract as `_secure`'s version — same arguments, same return-value shape (bool), same observed behavior on redirect. The contract test protects against drift if someone later modifies one copy without the other.

  **Patterns to follow:**
  - The function already exists as a reference in `scripts/comicskingdom_scraper_secure.py:147`. Port does not reimagine the flow.

  **Test scenarios:**
  - **Happy path:** `login_with_manual_recaptcha` exists in `_individual` with signature `(driver, username, password) -> bool`.
  - **Happy path:** Called with mocked driver where `current_url` transitions away from `/login` within the 120s wait loop, returns `True`. Assert `driver.execute_script` was called with the expected credential-filling JS (same pattern as `_secure`).
  - **Error path:** Mocked driver where `current_url` never leaves `/login` within the wait loop returns `False` (or whatever `_secure`'s current failure return is — match it exactly).
  - **Error path:** Username field not findable on any of the three selectors returns `False` without raising.
  - **Contract test:** `_individual.login_with_manual_recaptcha.__code__.co_argcount == _secure.login_with_manual_recaptcha.__code__.co_argcount` and both accept the same positional arguments. (Primitive but catches accidental signature drift; expand with a shared input/output fixture if it feels thin.)

  **Verification:**
  - All test scenarios pass.
  - A manual run of `scripts/reauth_comicskingdom.py` — after Unit 4 lands, not during Unit 2 — completes login as it does today. (Not this unit's verification, but Unit 2 is the enabling piece and should be reviewed with that downstream check in mind.)

- [ ] **Unit 3: Profile-aware authentication flow with empty-profile detection**

  **Goal:** Teach `authenticate_with_cookies` to branch on `use_profile`. When `True`: skip `load_cookies` entirely, check authentication, and if the profile is empty (no stored session, redirected to `/login`), emit a distinct "profile not seeded" message rather than the legacy reauth message. When `False`: behave exactly as today.

  **Requirements:** R1, R2, R3, R4, R6.

  **Dependencies:** Unit 1 (needs the `use_profile` flag in `setup_driver`).

  **Files:**
  - Modify: `scripts/comicskingdom_scraper_individual.py`
  - Modify: `tests/test_comicskingdom_scraper.py`

  **Approach:**
  - Extend `authenticate_with_cookies(driver, config)` signature or add a sibling function; reuse the existing name if a `use_profile` flag can be read from config or an environment variable. Preferred: extend signature to `authenticate_with_cookies(driver, config, use_profile=False)`, and thread the flag through `main` from an argparse `--no-profile`/`--use-profile` switch (default mirrors `setup_driver`'s default post-Unit-5).
  - When `use_profile=True`:
    1. Skip the cookie-age check, skip `load_cookies` entirely.
    2. Call `is_authenticated(driver)`.
    3. If `True`, print a success message, return `True`.
    4. If `False` — this means the profile is empty or its stored session expired. Check whether the profile directory is empty (e.g., lacks Chrome's standard session files: `Default/Cookies`, `Default/Login Data`). If empty: print `"⚠️  Chrome profile at ~/.comicskingdom_chrome_profile has no stored session. Run scripts/reauth_comicskingdom.py to seed it."` and return `False`. If non-empty but auth check failed: print the existing `"❌ Authentication failed - please run reauth script"` message — session is genuinely expired.
  - Extend `load_config_from_env` with `require_credentials=True` parameter. Default `True` preserves today's behavior. When `False` (daily scrape with `use_profile=True`), `COMICSKINGDOM_USERNAME`/`PASSWORD` are optional and the config dict carries `None` for their values.
  - Update `main()` to call `load_config_from_env(require_credentials=not use_profile)`.
  - When `use_profile=False`: behavior is identical to today.
  - The "profile empty" detection can be heuristic. Initial approach: check for existence of `~/.comicskingdom_chrome_profile/Default/Cookies`. If that file does not exist, treat as empty. Chrome creates it on first authenticated use.

  **Patterns to follow:**
  - Existing `authenticate_with_cookies` branching style (if/else on `cookie_file.exists()` today).
  - Existing emoji+short-text log style.

  **Test scenarios:**
  - **Happy path:** `use_profile=True`, profile is non-empty, `is_authenticated` returns `True` → `authenticate_with_cookies` returns `True` without ever calling `load_cookies`. (Mock `load_cookies` and assert it was not called.)
  - **Happy path:** `use_profile=False` → behavior matches existing tests exactly (run the existing test scenarios with this flag set; they should still pass).
  - **Error path — empty profile:** `use_profile=True`, profile directory missing (or lacks `Default/Cookies`), `is_authenticated` returns `False` → captured stdout contains the "profile has no stored session" message, does *not* contain "Authentication failed - please run reauth script".
  - **Error path — expired session:** `use_profile=True`, profile directory populated (e.g., `Default/Cookies` file created as a fixture), `is_authenticated` returns `False` → captured stdout contains "Authentication failed - please run reauth script", does *not* contain the new empty-profile message.
  - **Integration — credentials optional:** `load_config_from_env(require_credentials=False)` returns a config dict when `COMICSKINGDOM_USERNAME`/`PASSWORD` are unset (use `monkeypatch.delenv`).
  - **Integration — credentials still required when requested:** `load_config_from_env(require_credentials=True)` still calls `get_required_env_var` and exits when env vars are missing.
  - **Integration — full flow mocked:** Calling `main(argv=['--date', '2026-04-18', '--output-dir', '/tmp/x', '--use-profile'])` with a mocked Chrome never calls `load_cookies`, prints the success message, and proceeds to scraping.

  **Verification:**
  - All test scenarios pass.
  - Manually run `python scripts/comicskingdom_scraper_individual.py --use-profile --show-browser --date $(date +%Y-%m-%d) --output-dir /tmp/ck_shapea_test` on the Mini. Expected: `setup_driver` logs profile path; `load_cookies` timing markers (added in PR #114) do NOT appear in output; `is_authenticated` timing marker shows ~1-3s (not 20-30s); scrape proceeds. (This is a one-time manual validation. Unit 5 repeats it as the cutover check.)

- [ ] **Unit 4: Rewrite `reauth_comicskingdom.py` to seed the profile**

  **Goal:** Replace reauth's current cookie-persistence flow with a profile-seeding flow. Break the import dependency on `_secure`. After this unit, `_secure` is imported only by `scripts/diagnose_ck_page.py`.

  **Requirements:** R7. Supports R1–R6 by providing the seed mechanism for the new auth flow.

  **Dependencies:** Units 1 (profile setup), 2 (login flow ported to `_individual`).

  **Files:**
  - Modify: `scripts/reauth_comicskingdom.py`
  - Modify: `tests/test_comicskingdom_scraper.py`

  **Approach:**
  - Change the import block: remove `from scripts.comicskingdom_scraper_secure import (setup_driver, load_config_from_env, authenticate_with_cookie_persistence)`; replace with `from scripts.comicskingdom_scraper_individual import setup_driver, load_config_from_env, login_with_manual_recaptcha`.
  - Replace the flow:
    1. Load config with `require_credentials=True` (reauth genuinely needs them).
    2. `setup_driver(show_browser=True, use_profile=True)` — launch Chrome with the profile directory, visible window.
    3. Call the ported `login_with_manual_recaptcha(driver, username, password)`.
    4. On success, print a confirmation message about the profile location (not about pickled cookies) and exit 0.
    5. No `save_cookies` call — Chrome persists the session into the profile automatically when the window closes cleanly.
  - Update user-facing prompts in the reauth script: replace any references to "cookies" or "cookie file" with "profile" where appropriate.
  - Delete the existing cookie-file-removal pre-step (the `if config['cookie_file'].exists(): config['cookie_file'].unlink()` block). The profile-seed flow does not clear existing pickled cookies; that's deferred cleanup.

  **Patterns to follow:**
  - The existing reauth script's argparse and user-prompt shape. Keep its conversational tone.
  - TinyView does not have a separate reauth script — its authentication seed happens the first time `setup_driver(show_browser=True)` is called manually. CK's reauth is a separate entry point because it's an explicit operator action tied to reCAPTCHA. Keep that shape.

  **Test scenarios:**
  - **Happy path:** Running `reauth_comicskingdom.py` with mocked `login_with_manual_recaptcha` returning `True` exits with code 0 and emits a success message that mentions the profile directory path.
  - **Error path:** `login_with_manual_recaptcha` returns `False` → script exits with non-zero code and emits the reauth-failed message.
  - **Integration — import wiring:** `reauth_comicskingdom.py` imports only from `scripts.comicskingdom_scraper_individual` (verify by `ast`-walking the file or by grep — adversarial check against accidentally importing from `_secure`).
  - **Edge case:** Profile directory does not exist at start → `setup_driver` creates it, login populates it, final state is a non-empty profile directory.

  **Verification:**
  - All test scenarios pass.
  - Manual run on the Mini (after Unit 3 is in): `python scripts/reauth_comicskingdom.py` with a freshly deleted `~/.comicskingdom_chrome_profile` (or a renamed one). Interactive reCAPTCHA solve succeeds. Profile directory is populated. Subsequent run of `python scripts/comicskingdom_scraper_individual.py --use-profile --show-browser --date $(date +%Y-%m-%d) --output-dir /tmp/x` authenticates without prompting and scrapes 153/153.

- [ ] **Unit 5: Flip daily scrape default to `use_profile=True` and validate cutover**

  **Goal:** Change `setup_driver`'s default from `use_profile=False` to `use_profile=True`. This single-line change is the production cutover. Validate over one overnight run before considering the migration complete.

  **Requirements:** R1, R2, R8. This is where R1/R2 actually take effect in production.

  **Dependencies:** Units 1, 2, 3, 4.

  **Files:**
  - Modify: `scripts/comicskingdom_scraper_individual.py` (default flip)
  - Modify: `tests/test_comicskingdom_scraper.py` (update affected tests)
  - Modify: `docs/STATUS.md` (session log entry)

  **Approach:**
  - Change `def setup_driver(show_browser=False, use_profile=False)` to `def setup_driver(show_browser=False, use_profile=True)`.
  - Change the default on any other function that took a `use_profile` parameter introduced in earlier units, if they exist (e.g., `main`'s argparse default). The CLI flag's semantic becomes `--no-profile` to opt out, not `--use-profile` to opt in.
  - Update tests that relied on the old default: any test that called `setup_driver()` expecting no `--user-data-dir` must now explicitly pass `use_profile=False`, or the expectation must be flipped. The existing Unit 1 tests already cover both `True` and `False` branches; this unit updates which one matches the default.
  - No master script change. No Mini wrapper change. The `CK_SCRAPER_EXTRA_ARGS="--show-browser"` continues to compose with the new default.
  - Update `docs/STATUS.md`: add a session log entry capturing the cutover date, the observed Unit 1 diagnosis, and the Shape A implementation reference.

  **Patterns to follow:**
  - Existing `setup_driver(show_browser=False)` default style.
  - `docs/STATUS.md` session log format.

  **Test scenarios:**
  - **Happy path:** `setup_driver()` with no arguments now produces a `--user-data-dir=` option.
  - **Backward compat:** `setup_driver(use_profile=False)` still exists and still produces the pre-Shape-A Chrome options.
  - **Integration:** `main()` invoked without any profile-related CLI flag defaults to profile mode, calls `is_authenticated` directly without `load_cookies`.

  **Verification:**
  - All tests pass.
  - Manual end-to-end run on the Mini matching the LaunchD invocation shape: `./scripts/mini_master_update.sh` (or just the `_individual` invocation with `--show-browser --date $(date +%Y-%m-%d) --output-dir data`). Expected: `[HH:MM:SS.fff] load_cookies: driver.get(comicskingdom.com) START` timing marker DOES NOT APPEAR in the output (the code path is not invoked under profile mode). `[HH:MM:SS.fff] is_authenticated: driver.get(/favorites) START` appears and completes in ~1-3s (no 20s slow-walk). Scrape emits 153/153.
  - One overnight LaunchD run at 3 AM that succeeds: no `Error loading cookies` messages, no `Authentication failed - please run reauth script` messages, CK JSON written with 153 entries.
  - STATUS.md session log entry describes the cutover and references this plan.
  - If the overnight run fails: revert the one-line default change (`use_profile=True` → `use_profile=False`), investigate via the Unit 1 instrumentation output, and re-plan. The backward-compat code path is intact and production will fall back to the pre-plan behavior on the next run.

## System-Wide Impact

- **Interaction graph:** `reauth_comicskingdom.py` now imports from `_individual` instead of `_secure`. `_secure`'s remaining consumer is `scripts/diagnose_ck_page.py`. The master script and Mini wrapper are unchanged.
- **Error propagation:** Two new distinct messages exist on the auth failure path. Operators (and future log-watchers) can differentiate three states: (a) profile not seeded → human action needed: reauth; (b) session expired → human action needed: reauth; (c) unexpected failure → investigate.
- **State lifecycle risks:** The first LaunchD run after deploy requires a seeded profile. If the reauth hasn't happened yet, the scrape fails cleanly with message (a). This is the scenario R6 addresses: the error message is unambiguous rather than reproducing the "please run reauth" misdiagnosis this whole plan is trying to eliminate.
- **API surface parity:** `_individual`'s CLI contract (`--date`, `--output-dir`, `--show-browser`) is preserved. A new `--no-profile` (or `--use-profile=false`) CLI flag is added for debugging and for asymmetric-run comparisons. The master script does not set this new flag, so production runs under profile mode.
- **Integration coverage:** The smoke tests in `tests/test_comicskingdom_scraper.py` assert control flow through the auth branches. End-to-end correctness (Chrome + profile + CK WAF) is confirmed by Unit 5's manual and overnight validation, not by tests.
- **Unchanged invariants:** Six-source pipeline structure, Phase 2→3 invariant guard, push-conflict recovery flow, 153-comic catalog expectation, `_individual`'s per-URL extraction strategy, `--show-browser` on the Mini, the 3 AM LaunchD schedule, Netlify auto-deploy on push.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| First LaunchD run under Shape A hits an unseeded profile and fails. | The failure is clean, isolated, and self-documenting (distinct "profile not seeded" message). Operator runs reauth and the next run succeeds. Deploy + reauth should happen in the same session (same-day deploy, reauth within minutes of merge). Documented in Unit 5's verification. |
| Chrome profile corruption from an ungraceful Mini shutdown or Chrome auto-update. | Recoverable via `rm -rf ~/.comicskingdom_chrome_profile && python scripts/reauth_comicskingdom.py`. Document the recovery procedure in `docs/STATUS.md`'s operational section as part of Unit 5. TinyView has this same failure mode and recovery; this is an accepted ops cost. |
| `--user-data-dir` + `--headless=new` interaction breaks something the mocked tests don't catch. | Production never runs headless (Mini wrapper forces `--show-browser`). The mocked tests cover the flag composition at the options-list level; a rare dev-mode headless run can be diagnosed via the Unit 1 instrumentation if it surfaces. If systematic, force `use_profile=True` to imply `show_browser=True`. |
| CK's WAF starts slow-walking the profile-authenticated first request too (e.g., upstream tightens fingerprinting and starts treating persistent-profile sessions as suspicious). | Unlikely given TinyView's clean track record, but if it happens the Unit 1 instrumentation will show it immediately — timing on `is_authenticated`'s `driver.get(/favorites)` will drift upward from the current ~2.7s baseline. Rollback path is a one-line default flip. |
| `login_with_manual_recaptcha` port introduces drift between `_individual`'s and `_secure`'s copies before `_secure` is deleted. | Unit 2 contract test asserts signature parity. Short window — `_secure` deletion follow-up happens within a week of Unit 5's validation. |
| `data/comicskingdom_cookies.pkl` becomes stale/misleading. | Left in place intentionally. It's dead data under Shape A but the pickled-cookie code path is still there as a rollback. Cleanup is a separate PR once Shape A has a week of stable runs. |
| Pickle deserialization path remains a known-risk attack surface during the coexistence window (flagged by security review on the parent plan). | Host is single-operator Mini with no untrusted writers. Window is bounded to one week of Shape A validation, then the pickle path and file both go away. Risk accepted. |

## Documentation / Operational Notes

- Unit 5 updates `docs/STATUS.md` session log with the cutover summary and the reliability gain.
- After Unit 5, `docs/LOCAL_AUTOMATION_README.md` may reference pickled cookies in its CK section. Grep for mentions during Unit 5; update to reference the profile directory and the `reauth_comicskingdom.py` workflow instead.
- Unit 4's PR body should call out the `_secure` dependency break as the specific outcome that enables the follow-up cleanup. Makes the follow-up obvious to a reviewer who sees only Unit 4.
- The Unit 1 instrumentation markers from PR #114 stay in place through this plan. Their absence or presence in a day's log is a binary signal for "was Shape A active on this run." Remove in a follow-up once Shape A has a month of stable runs.

## Sources & References

- **Parent plan:** [docs/plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md](2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md) — this plan implements its Unit 3 Shape A.
- **Origin brainstorm:** [docs/brainstorms/2026-04-18-001-comicskingdom-scraper-reliability.md](../brainstorms/2026-04-18-001-comicskingdom-scraper-reliability.md)
- **Unit 1 findings:** [docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md](../solutions/logic-errors/comicskingdom-hang-diagnosis.md)
- **Institutional context:** [docs/internal/COMICSKINGDOM_ANALYSIS.md](../internal/COMICSKINGDOM_ANALYSIS.md), [docs/internal/RECAPTCHA_SOLUTIONS.md](../internal/RECAPTCHA_SOLUTIONS.md)
- **Reference implementation:** `scripts/tinyview_scraper_secure.py` (profile pattern), `scripts/tinyview_scraper_local_authenticated.py` (call-site pattern)
- **Files being modified:** `scripts/comicskingdom_scraper_individual.py`, `scripts/reauth_comicskingdom.py`, `tests/test_comicskingdom_scraper.py`
- **Related PRs:** #114 (Units 1 and 2 of parent plan), #115 (Unit 1 findings note), #116 (unrelated testenv cleanup)
- **Current failure log:** `logs/master_update.log` — contains the 16 renderer-timeout events that motivated this work.
