# Local Automation (Mac Mini)

This document describes how ComicCaster's daily feed pipeline runs in production — on a dedicated Mac Mini, scheduled by LaunchD, scraping all sources locally and pushing updates straight to `main` for Netlify to deploy.

An earlier hybrid design split scraping between a laptop (Comics Kingdom only) and GitHub Actions (everything else). That design was retired 2025-11-26. The GitHub Actions update workflows (`.github/workflows/update-feeds.yml`, `update-feeds-smart.yml`) still exist but have their `schedule` triggers commented out — they're emergency-only manual fallbacks now.

## Pipeline at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│  Mac Mini (openclaw user), 3:05 AM CST daily, LaunchD-triggered  │
│                                                                  │
│  Phase 1 — scrape 6 sources (sequential, fail-soft)              │
│    1. GoComics            (authenticated, Selenium)              │
│    2. Comics Kingdom      (authenticated, Selenium, visible      │
│                            browser — anti-bot blocks headless)   │
│    3. TinyView            (authenticated, 90-day window)         │
│    4. Far Side            (Selenium for New Stuff archive)       │
│    5. New Yorker                                                 │
│    6. Creators Syndicate                                         │
│                                                                  │
│  Phase 2 — generate feeds from scraped JSON (sequential)         │
│    GoComics / Comics Kingdom / TinyView / New Yorker /           │
│    Far Side / Creators → public/feeds/*.xml                      │
│                                                                  │
│  Invariant guard: each successful scrape must have written its   │
│  dated JSON file. Missing file → logged failure.                 │
│                                                                  │
│  Phase 3 — commit and push                                       │
│    git add data/*.json public/feeds/*.xml                        │
│    git commit                                                    │
│    git push (60s watchdog)                                       │
│      on rejection → save JSONs / fetch / reset --hard            │
│                     origin/main / restore JSONs /                │
│                     regenerate all feeds / commit / push once    │
└──────────────────────────┬───────────────────────────────────────┘
                           ▼
               ┌─────────────────────────┐
               │  Netlify (auto-deploy)  │
               │  on push to main        │
               └─────────────────────────┘
```

## Files

| Path | Purpose |
|---|---|
| `scripts/mini_master_update.sh` | **Production entrypoint.** Sets host-specific env (PATH, deploy key, CK `--show-browser`), execs the tracked master update |
| `scripts/local_master_update.sh` | Tracked master update — all pipeline logic lives here |
| `scripts/scrape_*.py`, `scripts/authenticated_scraper_secure.py`, `scripts/comicskingdom_scraper_individual.py`, `scripts/tinyview_scraper_local_authenticated.py` | Per-source scrapers, all write to `data/*.json` |
| `scripts/generate_*_feeds.py`, `scripts/generate_gocomics_feeds.py`, `scripts/generate_tinyview_feeds_from_data.py` | Per-source generators, all write to `public/feeds/*.xml` |
| `scripts/reauth_comicskingdom.py` | Manual CK cookie refresh (see below) |
| `scripts/SETUP_COMICSKINGDOM_AUTH.sh` | First-time CK auth setup helper |
| `~/Library/LaunchAgents/com.comiccaster.master.plist` | LaunchD job — triggers `mini_master_update.sh` at 03:05 |
| `~/Library/LaunchAgents/com.openclaw.caffeinate.plist` | Keeps the Mini from sleeping (`caffeinate -s` with KeepAlive) |
| `data/*.json` | Scraped source data — tracked in git as pipeline inputs |
| `data/farside_new_last_id.txt` | Cursor for Far Side "New Stuff" dedup |
| `data/comicskingdom_cookies.pkl` | CK session cookies (git-ignored) |
| `.env` | Credentials: `GOCOMICS_EMAIL`, `GOCOMICS_PASSWORD`, `COMICSKINGDOM_USERNAME`, `COMICSKINGDOM_PASSWORD`, `COMICSKINGDOM_COOKIE_FILE` |
| `logs/master_update.log` | Daily run log (rotated at 10MB) |
| `logs/launchd_stdout.log`, `launchd_stderr.log` | LaunchD-captured output |

## Host requirements (Mac Mini)

These are load-bearing — the pipeline won't run without them:

- **Active GUI session, auto-login enabled.** Comics Kingdom's anti-bot blocks headless Chrome, so the CK scraper uses `--show-browser`, which requires a real display.
- **`com.openclaw.caffeinate.plist` loaded** so the Mini never sleeps before the 3:05 AM run.
- **ChromeDriver at `~/bin/chromedriver`**, Chrome from Google's standard installer. Versions must match (Chrome 147 + ChromeDriver 147, etc.).
- **Deploy key at `~/.ssh/comiccaster_deploy`** with push access to the repo. Loaded per-run via `GIT_SSH_COMMAND` — not via ssh-agent, so no keychain prompt.
- **`.env` at repo root** with CK + GoComics credentials.
- **Python venv at `./venv/`**, `pip install -r requirements.txt` + `pip install -e .`.

## Environment a typical dev doesn't need

If you're running the pipeline on a laptop for development (not on the Mini), none of the host-specific wrapper logic applies:

```bash
source venv/bin/activate
bash scripts/local_master_update.sh
```

The CK scraper will run headless (no `CK_SCRAPER_EXTRA_ARGS`), which is fine for development. Whether CK anti-bot lets you through depends on the site's mood.

## Daily flow

1. **03:05:00** — LaunchD fires `mini_master_update.sh`, which exports `PATH`, `GIT_SSH_COMMAND`, `CK_SCRAPER_EXTRA_ARGS=--show-browser`, then execs `local_master_update.sh`.
2. **03:05:01–03:05:05** — SSH auth check against GitHub. If it fails, the run aborts cleanly (notification).
3. **03:05:05–03:30** — Phase 1 scrape. CK is the longest; a real Chrome window opens and closes.
4. **03:30–03:32** — Phase 2 generation (fast, no network).
5. **03:32** — Invariant guard verifies every successful scrape wrote its dated JSON.
6. **03:32–03:33** — Phase 3 commit + push. Usually first-try. Push recovery (see below) only engages on rejection.
7. **Netlify** — detects push within ~30s, rebuilds and deploys.

## Push-conflict recovery

If the push is rejected (typically because another commit landed on `main` between the pipeline's pull at Phase 1 and its push at Phase 3):

1. Save today's scrape JSONs to a `mktemp` staging directory.
2. `git fetch origin && git reset --hard origin/main` — pick up whatever landed.
3. Copy the saved JSONs back into `data/`.
4. Re-run every feed generator (all six are network-free when fed from data).
5. Commit the regenerated feeds, push once.

No `git pull --rebase`. That strategy explodes into hundreds of add/add + content conflicts across generated feed XMLs — we hit that on 2026-04-17 and it published a merge commit with unresolved `<<<<<<<` markers in several JSONs. If the recovery push also fails, the pipeline bails; tomorrow's run retries.

## Monitoring

Real-time tail during a manual invocation:

```bash
tail -f logs/master_update.log
```

The final line tells you the outcome:

```
ComicCaster Master Update Complete (ALL SUCCESS) - <timestamp>
```
or
```
ComicCaster Master Update Complete with FAILURES - <timestamp>
Failed steps: <comma-separated list>
```

macOS notifications fire on both outcomes (`osascript` in `local_master_update.sh`).

Netlify deploys are at https://app.netlify.com/sites/comiccaster/deploys (assuming you have access).

## Common operations

### Run on demand

```bash
bash scripts/mini_master_update.sh
```

This is a real production run: it scrapes sites, commits, and pushes. Do it during the day if you want to validate a change to the pipeline before the next 3 AM run.

### CK cookies expired (every ~60 days)

CK uses a reCAPTCHA login flow; cookies eventually expire. If `[2/6] Scraping Comics Kingdom` starts failing consistently:

```bash
source venv/bin/activate
python scripts/reauth_comicskingdom.py
```

A browser opens. Solve the reCAPTCHA, log in, let it finish. Fresh cookies land at `data/comicskingdom_cookies.pkl`. Next run will use them.

### LaunchD job unloaded / not firing

```bash
launchctl list | grep comiccaster.master
launchctl unload ~/Library/LaunchAgents/com.comiccaster.master.plist
launchctl load   ~/Library/LaunchAgents/com.comiccaster.master.plist
```

### Inspect a failed run

Most useful log sections (search within `logs/master_update.log`):

- `=== Phase 1:` — scrape progress
- `=== Verifying scrape invariants ===` — per-source data file check
- `=== Phase 3:` — commit + push
- `Engaging reset-regenerate recovery` — push-conflict recovery kicked in

## What not to do

- **Don't `git pull` with a merge strategy on the Mini manually.** The same conflict explosion that killed the automation on 2026-04-17 will bite you. Use `git fetch && git reset --hard origin/main` if you need to sync.
- **Don't edit `data/*.json` by hand to "fix" a feed.** The data files are authoritative pipeline inputs; the generators overwrite feeds from them each run. Fix the scraper if data is wrong.
- **Don't `launchctl load` the plist with `RunAtLoad` set to true.** We want strict 3:05 AM cadence, not a re-run every reboot.
- **Don't turn off `caffeinate`.** The Mini will sleep, miss the 3 AM window, and feeds will stall.

## Uninstalling

```bash
launchctl unload ~/Library/LaunchAgents/com.comiccaster.master.plist
rm              ~/Library/LaunchAgents/com.comiccaster.master.plist
```

The `com.openclaw.caffeinate.plist` is shared with other automation; don't unload it unless you know nothing else relies on it.
