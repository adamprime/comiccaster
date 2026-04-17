# AGENTS.md

This file provides guidance to AI coding assistants when working with this repository.

## Project Overview

ComicCaster generates RSS feeds for comics from multiple sources (GoComics, Comics Kingdom, TinyView, The Far Side). It uses a hybrid serverless/static site architecture deployed on Netlify, with daily automated feed updates run locally.

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

# Individual source generators (Phase 2 — reads JSON, writes public/feeds/*.xml; network-free)
python scripts/generate_gocomics_feeds.py
python scripts/generate_comicskingdom_feeds.py
python scripts/generate_tinyview_feeds_from_data.py
python scripts/generate_newyorker_feeds.py
python scripts/generate_farside_feeds.py
python scripts/generate_creators_feeds.py
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
   - `mini_master_update.sh` - Production entrypoint (sets host-specific environment, execs the tracked master update)
   - `local_master_update.sh` - Main daily update orchestrator
   - `scrape_*.py` and authenticated scrapers — per-source scrapers (Phase 1), each writes `data/<src>_$DATE.json`
   - `generate_*.py` — per-source generators (Phase 2), network-free, read the latest scraped JSON and write `public/feeds/*.xml`
   - `backfill_gocomics_feeds.py` — manual rate-limited recovery
   - `reauth_comicskingdom.py`, `SETUP_COMICSKINGDOM_AUTH.sh` — session refresh for Comics Kingdom

4. **functions/** - Netlify serverless functions
   - `generate-opml.js` - OPML bundle generation
   - `fetch-feed.js` - Feed preview functionality

5. **docs/** - Documentation
   - `docs/setup/` - Setup and configuration guides
   - `docs/internal/` - Internal/archived documentation

### Feed Update Process

Daily updates run on a dedicated always-on host, overnight:
1. **Phase 1 — scrape** the six sources (GoComics, Comics Kingdom, TinyView, New Yorker, Far Side, Creators Syndicate), each writing to `data/<src>_$DATE.json`.
2. **Phase 2 — generate** feeds from those JSONs. Each source has a dedicated generator; all are network-free.
3. **Invariant guard:** every successful scrape must have written its dated JSON file; missing files surface as failures.
4. **Phase 3 — commit and push.** On push rejection, recovery saves today's JSONs, resets to `origin/main`, restores them, and regenerates all feeds. Netlify auto-deploys on push.

See [docs/LOCAL_AUTOMATION_README.md](docs/LOCAL_AUTOMATION_README.md) for the operational details.

### Testing

- Test files in `tests/` mirror source structure
- Use pytest fixtures for common test data
- Run `pytest -v` before committing changes

### Deployment

- Push to main triggers Netlify deployment
- Feed XMLs are committed to the repository
- No manual deployment steps required
