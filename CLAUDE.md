# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ComicCaster is a web application that generates RSS feeds for comics from GoComics.com. It uses a hybrid serverless/static site architecture deployed on Netlify, with daily automated feed updates via GitHub Actions.

## Key Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt
pip install -e .
npm install

# Run tests
pytest -v
pytest -v --cov=comiccaster --cov-report=term-missing  # with coverage

# Start local development
netlify dev  # Full stack at http://localhost:8888
python run_app.py  # Flask only at http://localhost:5001

# Enable Flask debug mode for development only
FLASK_DEBUG=true python run_app.py  # With debug mode
```

### Feed Management
```bash
# Update all feeds
python scripts/update_feeds.py

# Generate single comic feed
python comiccaster.py --comic <comic-slug>

# Generate all feeds
python comiccaster.py --all

# Test comic scraping
python check_comic.py  # Interactive testing
python regenerate_feed.py  # Regenerate specific feeds
```

## Architecture

### Core Components

1. **comiccaster/** - Main Python package
   - `scraper.py` - Enhanced HTTP scraping with JSON-LD parsing for accurate comic detection
   - `feed_generator.py` - RSS feed generation using feedgen
   - `loader.py` - Comic configuration management
   - `web_interface.py` - Flask web application

2. **public/** - Static files served by Netlify
   - `feeds/*.xml` - Pre-generated RSS feeds
   - `comics_list.json` - Comic metadata
   - `index.html` - Main web interface

3. **functions/** - Netlify serverless functions (Node.js)
   - `generate-opml.js` - OPML bundle generation
   - `fetch-feed.js` - Feed preview functionality

### Feed Update Process

The system uses sophisticated scraping to accurately detect daily comics:
1. Fetches comic pages with JSON-LD structured data
2. Matches dates to find specific daily comics (not reruns)
3. Processes in parallel (8 workers)
4. Updates XML feeds in `public/feeds/`

Daily updates run automatically via GitHub Actions at 9 AM UTC.

### Testing Conventions

- Test files in `tests/` mirror source structure
- Use pytest fixtures for common test data
- Mark network tests with `@pytest.mark.network`
- Run coverage reports to ensure adequate testing

### Deployment

- Push to main branch triggers Netlify deployment
- Feed updates commit directly to repository
- No manual deployment steps required
- Build command in netlify.toml handles everything

## Important Implementation Details

1. **Comic Detection**: The system distinguishes between daily comics and "best of" reruns using date-matching in JSON-LD data
2. **Error Handling**: Graceful fallbacks when comics are unavailable or structure changes
3. **Performance**: Concurrent scraping with ThreadPoolExecutor, HTTP-only approach (no Selenium)
4. **Feed Format**: Standard RSS 2.0 with proper content encoding and metadata