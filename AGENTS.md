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
# Full daily update (runs all sources)
bash scripts/local_master_update.sh

# Individual source updates
python scripts/update_feeds.py                    # GoComics
python scripts/generate_comicskingdom_feeds.py   # Comics Kingdom
python scripts/generate_tinyview_feeds_from_data.py  # TinyView
python scripts/update_farside_feeds.py           # Far Side
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
   - `local_master_update.sh` - Main daily update orchestrator
   - `*_scraper_*.py` - Authenticated scrapers
   - Various feed generation scripts

4. **functions/** - Netlify serverless functions
   - `generate-opml.js` - OPML bundle generation
   - `fetch-feed.js` - Feed preview functionality

5. **docs/** - Documentation
   - `docs/setup/` - Setup and configuration guides
   - `docs/internal/` - Internal/archived documentation

### Feed Update Process

Daily updates run locally via LaunchD (3 AM CST):
1. Scrapes all sources (GoComics, Comics Kingdom, TinyView, Far Side)
2. Generates/updates XML feeds in `public/feeds/`
3. Commits and pushes to repository
4. Netlify auto-deploys on push

### Testing

- Test files in `tests/` mirror source structure
- Use pytest fixtures for common test data
- Run `pytest -v` before committing changes

### Deployment

- Push to main triggers Netlify deployment
- Feed XMLs are committed to the repository
- No manual deployment steps required
