# Local Automation

ComicCaster's daily feed pipeline runs on a dedicated always-on host, not in CI. All scrapers, all feed generators, and the commit/push step run together on that host; Netlify picks up the push and deploys.

An earlier hybrid design split scraping between a laptop (one source) and GitHub Actions (the rest). That was retired 2025-11-26. The GitHub Actions feed workflows still exist (`.github/workflows/update-feeds.yml`, `update-feeds-smart.yml`) with their schedules commented out — they're a manual fallback if the local host is unavailable.

## Pipeline at a glance

```
┌────────────────────────────────────────────────────────────────┐
│  Local host, daily overnight run (LaunchAgent)                 │
│                                                                │
│  Phase 1 — scrape 6 sources (sequential, fail-soft)            │
│    GoComics, Comics Kingdom, TinyView, Far Side,               │
│    New Yorker, Creators Syndicate                              │
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
└────────────────────────────┬───────────────────────────────────┘
                             ▼
                ┌─────────────────────────┐
                │  Netlify (auto-deploy)  │
                │  on push to main        │
                └─────────────────────────┘
```

## Files

| Path | Purpose |
|---|---|
| `scripts/mini_master_update.sh` | Production entrypoint — sets host-specific environment, execs the tracked master update |
| `scripts/local_master_update.sh` | Tracked master update — all pipeline logic lives here |
| `scripts/scrape_*.py` and per-source authenticated scrapers | Phase 1 scrapers; each writes to `data/*.json` |
| `scripts/generate_*.py` | Phase 2 generators; each reads `data/*.json` and writes to `public/feeds/*.xml` |
| `scripts/reauth_comicskingdom.py` | Manual Comics Kingdom session refresh |
| `data/*.json` | Per-source scraped data — tracked in git as pipeline inputs |
| `data/farside_new_last_id.txt` | Cursor for Far Side "New Stuff" dedup |
| `.env` | Per-source credentials (see below) |
| `logs/master_update.log` | Daily run log, rotated at 10MB |

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
- `COMICSKINGDOM_USERNAME`, `COMICSKINGDOM_PASSWORD`, `COMICSKINGDOM_COOKIE_FILE`

The Comics Kingdom cookie file is a binary pickle produced on first-time auth via `scripts/SETUP_COMICSKINGDOM_AUTH.sh` + `scripts/reauth_comicskingdom.py`. It expires roughly every 60 days and must be refreshed manually.

## Dev mode (not on the production host)

If you're running the pipeline on a laptop for development:

```bash
source venv/bin/activate
bash scripts/local_master_update.sh
```

Nothing in `mini_master_update.sh`'s host-specific environment is applied, so every scraper runs with defaults. One source may fail in this mode depending on upstream conditions; that's expected.

## Daily flow

1. LaunchAgent fires the wrapper script overnight.
2. The wrapper exports `PATH`, `GIT_SSH_COMMAND`, and `CK_SCRAPER_EXTRA_ARGS`, then `exec`s the tracked master update.
3. SSH auth check against GitHub. On failure, the run aborts cleanly and sends a notification.
4. Phase 1 scrape (the long part — Comics Kingdom dominates runtime).
5. Phase 2 feed generation (fast, no network).
6. Invariant guard verifies every successful scrape wrote its dated JSON file.
7. Phase 3 commit + push. If the first push is accepted, we're done.
8. Netlify detects the push and deploys within ~30 seconds.

## Push-conflict recovery

If the push is rejected (another commit landed on `main` between the pipeline's fetch and its push):

1. Save today's scrape JSONs to a `mktemp` staging directory.
2. `git fetch origin && git reset --hard origin/main`.
3. Copy the saved JSONs back into `data/`.
4. Re-run every feed generator. All are network-free when fed from data.
5. Commit the regenerated feeds, push once.

We do **not** use `git pull --rebase`. That strategy explodes into hundreds of conflicts across generated feed XMLs — we hit that on 2026-04-17 and it published a merge commit with unresolved conflict markers inside several JSONs. If the recovery push also fails, the pipeline bails and the next scheduled run retries.

## Monitoring

Real-time during a manual run:

```bash
tail -f logs/master_update.log
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

macOS notifications fire on both outcomes (see `osascript` in `local_master_update.sh`).

Netlify deploys: https://app.netlify.com/sites/comiccaster/deploys (maintainer access required).

## Common operations

### Run on demand

```bash
bash scripts/mini_master_update.sh
```

This is a real production run: it scrapes, commits, and pushes. Use it to validate a pipeline change before the next overnight cycle.

### Comics Kingdom session expired

If `Scraping Comics Kingdom` starts failing consistently, refresh the session:

```bash
source venv/bin/activate
python scripts/reauth_comicskingdom.py
```

A browser will open; complete the login flow. Fresh session state is saved automatically. Next run picks it up.

### LaunchAgent not firing

```bash
launchctl list | grep comiccaster.master
launchctl unload ~/Library/LaunchAgents/com.comiccaster.master.plist
launchctl load   ~/Library/LaunchAgents/com.comiccaster.master.plist
```

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
