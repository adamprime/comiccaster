# AGENTS.md

This file provides guidance to AI coding assistants when working with this repository.

## Project Overview

ComicCaster generates RSS feeds for comics from multiple sources (GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, Mr. Boffo). It uses a hybrid serverless/static site architecture deployed on Netlify, with daily automated feed updates run locally.

## Key Commands

### Development Setup
```bash
pip install -r requirements.txt
pip install -e .
npm install

# Run tests
pytest -v
pytest -v --cov=comiccaster --cov-report=term-missing

# Local development
netlify dev  # Full stack at http://localhost:8888
python run_app.py  # Flask only at http://localhost:5001
```

### Feed Management
```bash
# Full daily update (runs all sources through all phases)
bash scripts/local_master_update.sh

# Individual source scrapes (Phase 1 — produces data/<src>_$DATE.json)
python scripts/authenticated_scraper_secure.py         # GoComics
python scripts/comicskingdom_scraper_individual.py     # Comics Kingdom
python scripts/tinyview_scraper_local_authenticated.py # TinyView
python scripts/scrape_newyorker.py                     # New Yorker
python scripts/scrape_farside.py                       # Far Side
python scripts/scrape_creators.py                      # Creators Syndicate
python scripts/scrape_mrboffo.py                       # Mr. Boffo

# Individual source generators (Phase 2 — reads JSON, writes public/feeds/*.xml; network-free)
python scripts/generate_gocomics_feeds.py
python scripts/generate_comicskingdom_feeds.py
python scripts/generate_tinyview_feeds_from_data.py
python scripts/generate_newyorker_feeds.py
python scripts/generate_farside_feeds.py
python scripts/generate_creators_feeds.py
python scripts/generate_mrboffo_feeds.py
```

## Architecture

### Core Components

1. **comiccaster/** - Main Python package
   - `feed_generator.py` - RSS feed generation with multi-image support
   - `scraper_factory.py` - Factory pattern for selecting appropriate scraper
   - `*_scraper.py` - Source-specific scrapers
   - `loader.py` - Comic configuration management
   - `web_interface.py` - Flask web application

2. **public/** - Static files served by Netlify
   - `feeds/*.xml` - Pre-generated RSS feeds
   - `comics_list.json` - Comic metadata
   - `index.html` - Main web interface

3. **scripts/** - Update and utility scripts
   - `mini_master_update.sh` - Pass 1 production entrypoint (sets host-specific environment, execs the tracked master update)
   - `local_master_update.sh` - Pass 1 orchestrator (03:05, all seven sources)
   - `mini_master_pass2.sh` / `local_pass2_update.sh` - Pass 2 (13:00, GoComics only, `--merge` + rolling backfill)
   - `report_pipeline_failures.py` - Opens/comments/closes a GitHub issue per failing source (runs in Actions)
   - `check_pipeline_heartbeat.py` - Dead-man's switch for a pipeline that never ran
   - `check_scrape_counts.py` - Invariant guard's count half; per-source minimums in `SOURCE_RULES`
   - `check_ck_session.py` - CK cookie expiry (verifies a reauth took; cannot see a server-side logout)
   - `check_host_config.py` - Host auto-login / remote-access settings the LaunchAgents depend on
   - `scrape_*.py` and authenticated scrapers — per-source scrapers (Phase 1), each writes `data/<src>_$DATE.json`
   - `generate_*.py` — per-source generators (Phase 2), network-free, read the latest scraped JSON and write `public/feeds/*.xml`
   - `backfill_gocomics_feeds.py` — manual rate-limited recovery
   - `reauth_comicskingdom.py` — session refresh for Comics Kingdom

4. **functions/** - Netlify serverless functions
   - `generate-opml.js` - OPML bundle generation
   - `fetch-feed.js` - Feed preview functionality

5. **.github/workflows/** - CI and alerting
   - `pipeline-alert.yml` - Dispatched by both passes; creates failure issues as `github-actions[bot]`
   - `pipeline-heartbeat.yml` - Scheduled; alerts when no pipeline commit lands within 20h
   - `tests.yml` - pytest on 3.10/3.11/3.12 for PRs to `main`

6. **docs/** - Documentation
   - `docs/LOCAL_AUTOMATION_README.md` - Operational reference for the daily pipeline
   - `docs/internal/` - Internal/archived documentation

### Feed Update Process

Updates run on a dedicated always-on host, **twice daily** — Pass 1 at 03:05 (all sources) and Pass 2 at 13:00 (GoComics only, catching late political/editorial publishers):
1. **Phase 1 — scrape** the seven sources (GoComics, Comics Kingdom, TinyView, New Yorker, Far Side, Creators Syndicate, Mr. Boffo), each writing to `data/<src>_$DATE.json`.
2. **Phase 2 — generate** feeds from those JSONs. Each source has a dedicated generator; all are network-free.
3. **Invariant guard:** every successful scrape must have written its dated JSON file **and** filled it with a plausible number of entries; missing *or* empty/partial files surface as failures. Existence alone was satisfiable by an empty scrape — see `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md`.
4. **Preflights:** the CK session cookie and the host auto-login settings, both of which warn while there is still time to act.
5. **Phase 3 — commit and push.** On push rejection, recovery saves today's JSONs, resets to `origin/main`, restores them, and regenerates all feeds. Netlify auto-deploys on push.
6. **Alerting.** Every run dispatches `pipeline-alert.yml` with what failed and what it examined — on success too, since that is what closes issues for recovered sources. Scrape, invariant, push, SSH-preflight, CK-session, and host-config failures open a GitHub issue; feed generation and `git fetch` stay log-only.

The host **detects** failures but does not create the issues: GitHub sends no notification for an issue you author yourself, and the host authenticates as the repo owner. Issues are authored by `github-actions[bot]` instead. A separate scheduled heartbeat covers the case the reporter structurally cannot — a run that never happened. See `docs/LOCAL_AUTOMATION_README.md`.

See [docs/LOCAL_AUTOMATION_README.md](docs/LOCAL_AUTOMATION_README.md) for the operational details.

### Testing

- Test files in `tests/` mirror source structure
- Use pytest fixtures for common test data
- Run `pytest -v` before committing changes

### Deployment

- Push to main triggers Netlify deployment
- Feed XMLs are committed to the repository
- No manual deployment steps required
