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
python scripts/update_feeds.py  # GoComics feeds
python scripts/update_tinyview_feeds.py  # TinyView feeds

# Generate single comic feed
python comiccaster.py --comic <comic-slug>  # GoComics
python scripts/generate_tinyview_feed.py <comic-slug>  # TinyView

# Generate all feeds
python comiccaster.py --all  # GoComics
python scripts/generate_all_tinyview_feeds.py  # TinyView (parallel)

# Test comic scraping
python check_comic.py  # Interactive testing for GoComics
python scripts/test_tinyview_scraper.py  # Test TinyView scraping
python regenerate_feed.py  # Regenerate specific GoComics feeds
```

## Architecture

### Core Components

1. **comiccaster/** - Main Python package
   - `base_scraper.py` - Abstract base class for all scrapers
   - `gocomics_scraper.py` - Enhanced HTTP scraping with JSON-LD parsing for accurate comic detection
   - `tinyview_scraper.py` - Selenium-based scraper for TinyView's dynamic content
   - `scraper_factory.py` - Factory pattern for selecting appropriate scraper
   - `feed_generator.py` - RSS feed generation using feedgen with multi-image support
   - `loader.py` - Comic configuration management
   - `web_interface.py` - Flask web application

2. **public/** - Static files served by Netlify
   - `feeds/*.xml` - Pre-generated RSS feeds for both GoComics and TinyView
   - `comics_list.json` - Main comic metadata (includes all sources)
   - `tinyview_comics_list.json` - TinyView-specific comic list
   - `index.html` - Main web interface with tabbed navigation

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

1. **Comic Detection**: 
   - GoComics: Distinguishes between daily comics and "best of" reruns using date-matching in JSON-LD data
   - TinyView: Visits comic main page, finds date-specific strip links, then scrapes each strip page
2. **Error Handling**: Graceful fallbacks when comics are unavailable or structure changes
3. **Performance**: 
   - Concurrent scraping with ThreadPoolExecutor (8 workers)
   - GoComics: HTTP-only approach for speed
   - TinyView: Selenium WebDriver for dynamic content
4. **Feed Format**: Standard RSS 2.0 with proper content encoding and metadata
5. **Multi-strip Support**: TinyView comics can have multiple strips per day, all included in feed
6. **Update Frequency**:
   - GoComics: Checks last 10 days
   - TinyView: Checks last 15 days (accommodates less frequent updates)