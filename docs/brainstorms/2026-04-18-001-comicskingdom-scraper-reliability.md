---
title: "Comics Kingdom scraper reliability — architectural options"
type: brainstorm
status: in-review
date: 2026-04-18
---

# Comics Kingdom scraper reliability — architectural options

## Why this doc exists

Comics Kingdom is by far the most unreliable source in the daily pipeline. Other sources fail occasionally; CK fails routinely, and every failure looks — in the logs — like a cookie expiry that demands weekly manual reauth. Evaluation on 2026-04-18 showed the failures are misattributed, and the production scraper has several structural weaknesses that a band-aid retry won't address.

This brainstorm enumerates architectural options, names the tradeoffs explicitly, and ends with a recommendation.

## What we actually observe

### The failure mode isn't what the error message says

In the current `master_update.log` window (roughly 2026-03-27 → 2026-04-18), `❌ Comics Kingdom scraping failed` appears 16 times. Almost every event has the same fingerprint:

```
📅 Cookie file is [1–4] days old
❌ Error loading cookies: Message: timeout: Timed out receiving message from renderer: 29.xxx
❌ Authentication failed - please run reauth script
```

Cookies 1–4 days old are not expired (they're valid for ~60). The failure is a Chrome renderer hang on `driver.get("https://comicskingdom.com")` inside `load_cookies()`. The scraper catches the exception, prints "please run reauth," and exits. We've been responding with manual reauth runs that "fix" the symptom — but what fixes it is spawning a fresh Chrome session, not new cookies.

This morning's (2026-04-18 03:13) failure: cookie file 1 day old, renderer timeout 29.931s. The manual reauth + rerun at 11:28 succeeded on the very first cookie load with a fresh Chrome session.

### Two CK scrapers coexist, with divergent capabilities

| | `comicskingdom_scraper_individual.py` | `comicskingdom_scraper_secure.py` |
|---|---|---|
| Invoked by master script? | **Yes** (since 2025-11-15) | **No** |
| Invoked by reauth helper? | No | Yes (for cookie persistence flow) |
| Extraction strategy | 153 sequential page visits (`/{slug}/{date}`) | One favorites-page visit with load-more + lazy-image handling |
| Chrome session duration | ~6.5 min | ~1–2 min |
| Popup / interstitial dismissal | No | Yes |
| Diagnostic snapshot on failure | No | Yes (`data/ck_diagnostics/`) |
| Last substantive change | 2025-11-15 | 2026-04-09 (rewrite for CK site redesign) |
| Test coverage | None | None |

The 2026-04-09 session rewrote `_secure` in response to CK's site redesign. STATUS.md credits this work with restoring CK extraction (0 → 102 comics). But `_secure` has never been wired into the master script. The reason production has kept working is that `_individual` uses a different extraction strategy (per-URL visits) that was unaffected by the favorites-page redesign — effectively by accident, not by design.

### Architectural asymmetry with TinyView explains the reliability gap

| | Comics Kingdom | TinyView |
|---|---|---|
| Session persistence | Pickled cookies (~12 KB) | Persistent Chrome profile (~409 MB at `~/.tinyview_chrome_profile`) |
| Startup cost | `driver.get(domain) + sleep(2) + add_cookie(each)` — ~3–30s, sometimes hangs | `--user-data-dir=<profile>` — Chrome manages the session natively |
| Observed reauth frequency | Weekly+ | Essentially never |

The startup ritual for pickled cookies **is the operation that's hanging** in the production failures. TinyView's profile-based approach sidesteps the hang entirely because Chrome has everything it needs at process start — no page load required to "rehydrate" the session.

### Test coverage

No files under `tests/` exercise either CK scraper. `test_authenticated_scraper.py` covers GoComics (per the 2026-03-31 session notes). `test_tinyview_scraper.py` covers TinyView. CK is a test desert, which constrains our refactor appetite.

## Failure mode analysis

Before picking options, enumerate the failure modes we actually need to cover:

1. **F1 — Transient Chrome/renderer hang** (observed repeatedly). Resolved by a fresh Chrome session.
2. **F2 — Genuine cookie expiry** (observed every ~60 days by design). Requires human reauth.
3. **F3 — Site redesign breaks extraction** (observed 2026-04-09). Needs code update, ideally caught early by observable snapshots.
4. **F4 — Upstream popup/interstitial blocks interaction** (observed historically; `_secure` has defense, `_individual` doesn't).
5. **F5 — Silent partial scrape** (e.g., 50/153 extracts when site is flaky). Undetectable today because the invariant guard only checks file existence.
6. **F6 — Anti-bot challenge** (worse on headless; current mitigation is `--show-browser` on the Mini).

A "fix it right" direction needs to handle F1, F4, F5 structurally (these are our bugs) and fail loudly/cleanly on F2, F3, F6 (these require human intervention).

## Non-goals

- **Not** adding a second host or cloud-based scraping. The Mini's GUI + always-on nature is what gets us past anti-bot; moving to CI is a separate and much larger decision.
- **Not** trying to eliminate the ~60-day reauth. That's inherent to CK's session lifetime and reCAPTCHA gating.
- **Not** switching CK off Selenium. No known public API; the site is JS-heavy.
- **Not** paralellizing the per-URL scrape. Concurrency against CK will trip anti-bot faster than any reliability win.

## Options considered

### Option A — Minimal retry fix

Add bounded retry on renderer timeout in `load_cookies` and `is_authenticated`: on exception, quit the driver, spin up a new one, try once more. Differentiate "Chrome hung" from "cookies rejected" in the error message.

**Addresses:** F1.
**Doesn't address:** F4, F5. Still no popup handling in production. Still no silent-regression guard.
**Cost:** ~30 lines in `_individual`. No dependency changes.
**Risk:** Low. The retry covers the exact observed failure class with no architectural change.

### Option B — Consolidate on `_secure` (favorites-page strategy)

Switch the master script to invoke `_secure`. Delete `_individual`. Inherits popup handling, lazy-image loading, diagnostic snapshots, and a 4× shorter Chrome session.

**Addresses:** F1 (shorter session → less exposure), F4, F5 (diagnostic snapshots make partial scrapes visible post-hoc).
**Doesn't address:** Cookie startup ritual still present; F1 still possible. No test safety net for the switch.
**Cost:** Switch one line in master script; run full scrape locally to validate; likely rework the reauth flow's assumptions.
**Risk:** **Medium-high.** `_secure` depends on the favorites page, which has been redesigned once (2026-04-09) and will be redesigned again. `_individual`'s per-URL approach survived the last redesign because individual pages are the stable contract. Switching to `_secure` trades one fragility for another, and we have zero test coverage to detect regressions.

### Option C — Port to persistent-profile auth (TinyView pattern)

Replace the pickled-cookie dance with `--user-data-dir=~/.comicskingdom_chrome_profile`. Reauth writes into the profile (by logging in with Chrome and letting Chrome remember). Daily scrape starts Chrome with the profile flag; no `driver.get(domain) + add_cookie` ritual.

**Addresses:** F1 (eliminates the startup operation that hangs). Cleaner error semantics for F2.
**Doesn't address:** F4, F5.
**Cost:** Non-trivial. Profile-based reauth flow needs a rewrite. Chrome profile costs ~400 MB on disk. Must coexist with `--show-browser` (both can be set). First-run migration: the existing reauth script needs to be updated or replaced.
**Risk:** **Low-to-medium.** The pattern is proven in TinyView. Main risks are the reauth rewrite and the one-time migration from pickled cookies.

### Option D — Hybrid: `_secure` extraction + profile-based auth

Combine B and C. Get the favorites-page speed, the popup handling, the diagnostic snapshots, *and* the robust session.

**Addresses:** F1, F4, F5.
**Doesn't address:** F3 (favorites-page fragility is still present, just with more warning).
**Cost:** Both B and C combined. Most ambitious.
**Risk:** **High.** Two simultaneous structural changes with no test safety net. If something breaks, we can't isolate cause.

### Option E — Dual-path with fallback

Try `_secure` (fast path). On any failure, fall back to `_individual` (slow but stable). Keep both code paths.

**Addresses:** F1 (fallback compensates), F4 (primary path has handling).
**Doesn't address:** Complexity tax forever. Two code paths to maintain, one test desert to cover twice.
**Cost:** Orchestration logic; per-run time budget doubles in worst case.
**Risk:** Medium. Graceful degradation is tempting, but "two paths forever" is a maintenance burden we've already accidentally fallen into once (the `_individual`/`_secure` split). Explicitly codifying it is a local minimum.

## Recommendation

**A + C, in that order, as separate changes, with tests added in between.**

### Why

1. **A (minimal retry)** targets the #1 observed failure with a small, surgical change. It stops the false "please run reauth" spam and recovers transparently from the 30s renderer hang. Low risk, high leverage, worth doing immediately even if we also do C.

2. **C (profile-based auth)** is the structural fix for F1. TinyView has been running this pattern for years with no auth-related failures — it's not a bet, it's a proven pattern in this very codebase. It replaces the exact operation that's hanging, rather than just retrying when it does.

3. **Tests between A and C.** Add at least a smoke test for CK scraper initialization and a unit test for `load_cookies` error handling. Without this, C's rewrite has no safety net.

### Why not B / D

Both depend on the favorites-page extraction, which is structurally more fragile than per-URL visits. The 2025-11-15 decision to build `_individual` and switch to it was likely correct: favorites-page scraping broke again on 2026-04-09, while per-URL visits kept working. Switching back, even with `_secure`'s 2026-04-09 rewrite, inherits that fragility. **We can separately port `_secure`'s popup-dismissal helper into `_individual`** — that gets the F4 win without betting on the whole extraction strategy.

### What to do with F4 (popups) and F5 (silent partial scrape)

These should each be small separate units in the implementation plan, not wrapped into the auth work:

- **F4:** Copy the popup-dismissal helper from `_secure` into `_individual` (or a shared module). ~30 lines.
- **F5:** Add a CK-specific invariant: if the scrape wrote < N entries where N = 0.9 × catalog size, treat as failure. Similar guards for the other sources could follow.

### What to do with `_secure`

Don't delete yet. Keep it around as a reference implementation until `_individual` has feature parity (popup handling, diagnostics). Then delete in a follow-up to avoid drift.

### Rejected: "delete `_individual` and use `_secure`"

Already argued above under Option B. To crystallize: `_individual` is the production path precisely *because* per-URL visits are more resilient to CK's site redesigns. `_secure`'s favorites-page approach failed on 2026-04-09 and had to be rewritten; there is no reason to assume the next redesign won't do the same thing.

## Open questions

- Should the retry in A be one retry, two, or exponential backoff? (Leaning one retry — any more and we're burning the overnight window.)
- Does the profile approach need `--show-browser` the same way pickled-cookie approach does? (Likely yes — the `--show-browser` requirement is about anti-bot, not about session state.)
- When cookies expire (F2, ~60 days), does the profile itself need re-doing, or just a login within the profile? (Likely just a login; the profile persists.)

## What's *not* in this brainstorm

This doc does not decide the direction — the accompanying decision record does that. It also doesn't lay out the implementation — the accompanying plan does that. Kept here intentionally: the tradeoff comparison and the reasoning for the recommended path, so future sessions have something to argue against if they disagree.
