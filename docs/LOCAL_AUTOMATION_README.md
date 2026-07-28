# Local Automation

ComicCaster's daily feed pipeline runs on a dedicated always-on host, not in CI. All scrapers, all feed generators, and the commit/push step run together on that host; Netlify picks up the push and deploys.

An earlier hybrid design split scraping between a laptop (one source) and GitHub Actions (the rest). That was retired 2025-11-26. `.github/workflows/update-feeds.yml` is kept as a manual-only emergency fallback if the local host is unavailable.

## Pipeline at a glance

```
┌────────────────────────────────────────────────────────────────┐
│  Local host — Pass 1, 03:05 daily (LaunchAgent)                │
│                                                                │
│  Phase 1 — scrape 7 sources (sequential, fail-soft)            │
│    GoComics, Comics Kingdom, TinyView, Far Side,               │
│    New Yorker, Creators Syndicate, Mr. Boffo                   │
│                                                                │
│  Phase 2 — generate feeds from scraped JSON                    │
│    one script per source, all network-free                     │
│                                                                │
│  Invariant guard: each successful scrape must have written     │
│  its dated JSON file. Missing file → logged failure.           │
│                                                                │
│  Phase 3 — commit and push (with recovery on rejection)        │
│    save JSONs / fetch / reset --hard origin/main / restore     │
│    JSONs / regenerate feeds / commit / push once               │
└──────────────┬─────────────────────────────┬───────────────────┘
               ▼                             ▼
  ┌─────────────────────────┐   ┌────────────────────────────────┐
  │  Netlify (auto-deploy)  │   │  gh workflow run               │
  │  on push to main        │   │    → pipeline-alert.yml        │
  └─────────────────────────┘   │  opens / comments / closes     │
                                │  GitHub issues per source      │
                                └────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  Local host — Pass 2, 13:00 daily (LaunchAgent)                │
│                                                                │
│  GoComics only. Re-scrapes with --merge and a rolling backfill │
│  to catch political/editorial cartoonists who publish after    │
│  the 03:05 window, regenerates GoComics feeds, commits,        │
│  pushes, and reports through the same alert workflow.          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  GitHub Actions — heartbeat, 11:00 UTC daily                   │
│                                                                │
│  No pipeline commit on main within 20h → open an issue.        │
│  Runs off-host on purpose: it must still fire when the host    │
│  itself is asleep, offline, or dead.                           │
└────────────────────────────────────────────────────────────────┘
```

## Files

| Path | Purpose |
|---|---|
| `scripts/mini_master_update.sh` | Pass 1 production entrypoint — sets host-specific environment, execs the tracked master update |
| `scripts/local_master_update.sh` | Tracked Pass 1 update — all seven sources; the main pipeline logic lives here |
| `scripts/mini_master_pass2.sh` | Pass 2 production entrypoint — same wrapper pattern, no Comics Kingdom flag |
| `scripts/local_pass2_update.sh` | Tracked Pass 2 update — GoComics only, `--merge` plus rolling backfill |
| `scripts/catchup_master_update.sh` | Login-triggered safety net — runs the master update only if today's GoComics data file is missing |
| `scripts/scrape_*.py` and per-source authenticated scrapers | Phase 1 scrapers; each writes to `data/*.json` |
| `scripts/generate_*.py` | Phase 2 generators; each reads `data/*.json` and writes to `public/feeds/*.xml` |
| `scripts/report_pipeline_failures.py` | Opens / comments / closes the GitHub issue for each failing source. Runs in Actions, not on the host (see Failure alerting) |
| `scripts/check_pipeline_heartbeat.py` | Dead-man's switch — alerts when no pipeline commit has landed in 20h |
| `scripts/check_ck_session.py` | Reads the CK token expiry; used by the reauth script and the daily expiry alert |
| `.github/workflows/pipeline-alert.yml` | Dispatched by both passes; runs the reporter under `GITHUB_TOKEN` |
| `.github/workflows/pipeline-heartbeat.yml` | Scheduled 11:00 UTC; runs the heartbeat check |
| `scripts/reauth_comicskingdom.py` | Manual Comics Kingdom session refresh |
| `data/*.json` | Per-source scraped data — tracked in git as pipeline inputs |
| `data/farside_new_last_id.txt` | Cursor for Far Side "New Stuff" dedup |
| `.env` | Per-source credentials (see below) |
| `logs/master_update.log` | Pass 1 run log, rotated at 10MB |
| `logs/pass2_update.log` | Pass 2 run log, rotated at 10MB |

## Host requirements

These are the load-bearing assumptions the pipeline relies on. Detailed provisioning steps live in operator-only notes, not this public doc.

- An always-on host with an active interactive user session (not a headless server). One source requires a real browser session to scrape; the rest tolerate headless.
- ChromeDriver installed and on `PATH`, version-matched to Chrome.
- Git push authenticated via a deploy key wired into `GIT_SSH_COMMAND` by the wrapper script. Not ssh-agent — avoids any keychain prompt at overnight runtime.
- The system must not sleep before the run; a separate LaunchAgent handles that.
- A Python venv at `./venv/` with `requirements.txt` installed and the package in editable mode (`pip install -e .`).

## Credentials

`.env` at the repo root, git-ignored. Variables consumed by the scrapers:

- `GOCOMICS_EMAIL`, `GOCOMICS_PASSWORD`

Comics Kingdom does not use env vars. Session state lives in a Chrome profile at `~/.comicskingdom_chrome_profile/`, seeded by `python scripts/reauth_comicskingdom.py`.

**CK's token lasts exactly 7 days** — measured from the cookie, not estimated. The operator reauths weekly, so the margin is hours, not days: a reauth that fails to mint a new token means a failed run the next morning (2026-07-28). Two guards:

- `scripts/reauth_comicskingdom.py` reads the expiry before and after login and tells you whether it **actually moved**. Trust that line rather than the browser looking logged in. It exits non-zero if the expiry did not change.
- The daily run checks the expiry and opens a `[pipeline] Comics Kingdom session needs a reauth` issue when fewer than 2 days remain, so a silent reauth failure surfaces the same day instead of as an outage.

Check it any time:

```bash
python scripts/check_ck_session.py
```

Let the reauth script close the browser. Closing the window by hand can leave Chrome's new cookies unflushed — the leading hypothesis for the 2026-07-28 failure.

## Dev mode (not on the production host)

If you're running the pipeline on a laptop for development:

```bash
source venv/bin/activate
bash scripts/local_master_update.sh
```

Nothing in `mini_master_update.sh`'s host-specific environment is applied, so every scraper runs with defaults. One source may fail in this mode depending on upstream conditions; that's expected.

## Daily flow

The pipeline runs **twice a day**: Pass 1 at 03:05 covers all seven sources, Pass 2 at 13:00 re-scrapes GoComics only.

### Pass 1 — 03:05, all sources

1. LaunchAgent (`com.comiccaster.master`) fires the wrapper script overnight.
2. The wrapper exports `PATH`, `GIT_SSH_COMMAND`, and `CK_SCRAPER_EXTRA_ARGS`, then `exec`s the tracked master update.
3. SSH auth check against GitHub. On failure the run aborts cleanly, notifies, and dispatches a `preflight` alert — this abort happens *before* any scraping, so it would otherwise be the quietest failure of all.
4. Phase 1 scrape (the long part — Comics Kingdom dominates runtime).
5. Phase 2 feed generation (fast, no network).
6. Invariant guard verifies every successful scrape wrote its dated JSON file.
7. Phase 3 commit + push. If the first push is accepted, we're done.
8. Netlify detects the push and deploys within ~30 seconds.
9. The run dispatches `pipeline-alert.yml` with what failed and what it examined — on every run, success included, because that is what closes issues for sources that have recovered.

### Pass 2 — 13:00, GoComics only

Runs `com.comiccaster.pass2` → `scripts/mini_master_pass2.sh`. Re-scrapes GoComics with `--merge` and a rolling backfill (default 3 days), regenerates GoComics feeds, then commits, pushes, and alerts exactly as above. This catches political and editorial cartoonists who publish after the 03:05 window.

Pass 2 reports `--covered gocomics,push,preflight` and nothing else. That scoping is load-bearing: it examined no other source, so it must never close another source's issue.

### Heartbeat — 11:00 UTC, on GitHub

`pipeline-heartbeat.yml` checks whether any pipeline commit landed on `main` in the last 20 hours. It ignores human commits, so a code push cannot mask a pipeline that stopped running.

## Push-conflict recovery

If the push is rejected (another commit landed on `main` between the pipeline's fetch and its push):

1. Save today's scrape JSONs to a `mktemp` staging directory.
2. `git fetch origin && git reset --hard origin/main`.
3. Copy the saved JSONs back into `data/`.
4. Re-run every feed generator. All are network-free when fed from data.
5. Commit the regenerated feeds, push once.

We do **not** use `git pull --rebase`. That strategy explodes into hundreds of conflicts across generated feed XMLs — we hit that on 2026-04-17 and it published a merge commit with unresolved conflict markers inside several JSONs. If the recovery push also fails, the pipeline bails and the next scheduled run retries.

## Failure alerting

Both passes are unattended, so the primary failure signal is a **GitHub issue**, which arrives by email.

- **One issue per failing source**, titled `[pipeline] <Source> <kind> failed` and labelled `pipeline-failure`.
- **Recurrences comment** on the existing issue rather than opening duplicates.
- **Issues close themselves** when that source next succeeds, with a "Recovered" comment.
- **In scope:** scrape failures, invariant-guard violations, `git push` failures, and the SSH preflight abort. Feed-generation and `git fetch` failures are logged only.

Issues are identified by a `Pipeline-Failure-Key: <slug>` marker in the body, not by title or label — label-filtered listing on GitHub is eventually consistent and briefly omits freshly created issues.

### Why the host doesn't create the issues itself

The host detects failures, then dispatches `pipeline-alert.yml`; GitHub Actions creates the issue under `GITHUB_TOKEN`.

This is not indirection for its own sake. **GitHub sends no notification for an issue you author yourself**, and the host's `gh` is authenticated as the repo owner — so host-created alerts were invisible to the person meant to act on them. Authoring as `github-actions[bot]` makes them notify normally. See `docs/solutions/best-practices/github-self-authored-issues-dont-notify.md`.

Dispatching also preserves the reason detection lives on the host at all: `gh workflow run` is a direct API call, not a `git push`, so alerts still fire when pushing is the thing that broke.

### What issues deliberately omit

Issue bodies carry structured facts only — source, failure kind, run, date. **No run-log excerpt.** This repository is public and pipeline logs can contain account emails and cookie paths. Read the real log on the host.

## Monitoring

Real-time during a manual run:

```bash
tail -f logs/master_update.log   # or logs/pass2_update.log
```

The final line of every run reports the outcome:

```
ComicCaster Master Update Complete (ALL SUCCESS) - <timestamp>
```

or

```
ComicCaster Master Update Complete with FAILURES - <timestamp>
Failed steps: <comma-separated list>
```

macOS notifications fire on both outcomes (see `osascript` in `local_master_update.sh`). They are a convenience for someone sitting at the host; the GitHub issue is the signal that actually travels.

Open alerts: https://github.com/adamprime/comiccaster/issues?q=is%3Aopen+label%3Apipeline-failure

Netlify deploys: https://app.netlify.com/sites/comiccaster/deploys (maintainer access required).

## Common operations

### Run on demand

```bash
bash scripts/mini_master_update.sh
```

This is a real production run: it scrapes, commits, and pushes. Use it to validate a pipeline change before the next overnight cycle.

### Comics Kingdom session expired

When the daily run reports an auth failure, or a session alert arrives:

```bash
source venv/bin/activate
python scripts/reauth_comicskingdom.py
```

A browser opens; complete the login flow and **let the script close it**. The script then reports whether the expiry moved:

```
✅ Session renewed: expires 2026-08-04 11:21 UTC (7.0 days from now).
```

If it instead prints `❌ Session expiry did NOT move`, the login did not produce a new token — re-run it. That silent no-op is what caused the 2026-07-28 outage, and it is invisible in the browser.

### LaunchAgent not firing

```bash
launchctl list | grep comiccaster.master
launchctl unload ~/Library/LaunchAgents/com.comiccaster.master.plist
launchctl load   ~/Library/LaunchAgents/com.comiccaster.master.plist
```

### Forced overnight macOS updates skipping the 03:05 slot

The master LaunchAgent is user-level (`~/Library/LaunchAgents/...`) and only fires while a user is logged in. A forced macOS update that reboots overnight can leave the host at the loginwindow past 03:05 and the slot is silently skipped (incident 2026-05-26). Two layers of defence:

1. **Stop forced overnight installs.** macOS still notifies; operator installs on demand.

   ```bash
   sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates -bool false
   ```

2. **Catch-up LaunchAgent.** A second user-level agent runs at login and execs the master update only if today's `data/comics_<DATE>.json` is missing. Loaded once on the host:

   ```bash
   launchctl load -w ~/Library/LaunchAgents/com.comiccaster.catchup.plist
   ```

   The corresponding script lives in the repo at `scripts/catchup_master_update.sh`.

### A `[pipeline]` issue arrived

1. Read the issue: it names the source, the failure kind (`scrape`, `invariant`, `push`, `ssh`), and the run.
2. Pull the detail from the host log — the issue deliberately carries none:

   ```bash
   grep -n "❌\|Failed steps" logs/master_update.log | tail -20
   ```

3. Fix the cause. For Comics Kingdom this is usually an expired session (see above).
4. **Don't close the issue by hand.** The next successful run for that source closes it and posts a "Recovered" comment, which is also your confirmation that the fix worked.

Known-noisy by design: TinyView lapses and Comics Kingdom session expiries alert on the first failure — there is no consecutive-failure threshold. A long outage accrues one comment per run, which is the outage-duration record.

### A `Daily pipeline heartbeat failed` issue arrived

This one means something different: **no run happened at all**, rather than a source failing. Nothing on the host reported it, because nothing on the host ran.

```bash
launchctl list | grep comiccaster
tail -20 logs/master_update.log      # is the last entry from today?
```

Check that the host is awake and online, and that the LaunchAgents are loaded. See the forced-macOS-update section below for the usual cause.

### Test the alerting without breaking anything

```bash
gh workflow run pipeline-alert.yml \
  --field run=pass1 --field date="$(date +%Y-%m-%d)" \
  --field covered=tinyview --field failed=tinyview:scrape
```

Opens a real issue for a synthetic failure. Dispatch again with `--field failed=""` to watch it auto-close.

### Inspect a failed run

Useful sections to grep in `logs/master_update.log`:

- `=== Phase 1:` — scrape progress
- `=== Verifying scrape invariants ===` — per-source data file check
- `=== Phase 3:` — commit + push
- `Engaging reset-regenerate recovery` — push-conflict recovery kicked in

## What not to do

- **Don't manually `git pull` with the merge strategy on the host.** The same conflict explosion that broke the automation on 2026-04-17 will bite you. Use `git fetch && git reset --hard origin/main` to sync.
- **Don't hand-edit `data/*.json` to "fix" a feed.** The data files are authoritative pipeline inputs; generators overwrite feeds from them each run. Fix the scraper if the data is wrong.
- **Don't set `RunAtLoad` to true on the master LaunchAgent.** We want the overnight cadence, not a re-run every reboot.
- **Don't disable the host's anti-sleep setup.** The host will miss its overnight window and feeds will stall.
