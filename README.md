# ComicCaster

ComicCaster is a web application that generates RSS feeds for comics from GoComics.com and TinyView.com. It provides a unified interface to subscribe to your favorite comics through RSS, supporting both traditional daily comics and independent web comics.

## Features

### Core Functionality
- **500+ Comics Available**: Access to 400+ GoComics daily strips, 60+ political cartoons, and 29 TinyView independent comics
- **Multi-Source Architecture**: Unified interface for comics from different platforms using a modular scraper system
- **RSS Feed Generation**: Standard RSS 2.0 feeds compatible with all major feed readers
- **OPML Bundle Creation**: Generate custom bundles of comics for easy import into feed readers

### Advanced Features
- **Multi-Image RSS Support**: Full support for comics that publish multiple images/panels per day
- **Accurate Daily Comic Detection**: Distinguishes between current daily comics and "best of" reruns using JSON-LD parsing
- **Smart Update Scheduling**: Optimizes feed updates based on comic publishing patterns (daily, weekly, irregular)
- **Parallel Processing**: Uses 8 concurrent workers for efficient feed generation
- **Feed Health Monitoring**: Automated canary system detects and alerts on stale feeds

### User Interface
- **Tabbed Navigation**: Separate tabs for daily comics, political cartoons, and TinyView comics
- **Feed Preview**: Check comic content before subscribing
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Search and Filter**: Quickly find comics by name or category
- **Day-of-Week Filtering**: Feed titles include day abbreviations (Mon, Tue, Wed, etc.) allowing users to filter by specific days in their RSS reader (e.g., show only Sunday comics)

### Technical Features
- **Modular Scraper System**: Extensible architecture with base scraper class and source-specific implementations
- **Granular Source Tracking**: Each comic tracked with specific source field for proper scraper selection
- **Error Resilience**: Graceful handling of missing comics, site changes, and network issues
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## Quick Start

Visit [ComicCaster](https://comiccaster.xyz) to:
1. Browse available comics and preview their feeds
2. Subscribe to individual comics using their RSS feed URLs
3. Create custom bundles by selecting multiple comics and generating an OPML file
4. Import the OPML file into your favorite RSS reader

## Local Development

1. Clone the repository:
```bash
git clone https://github.com/adamprime/comiccaster.git
cd comiccaster
```

2. Install dependencies:
```bash
npm install
```

3. Start the Netlify development server:
```bash
netlify dev
```

4. Visit `http://localhost:8888` in your browser

### Running Flask Directly (Optional)

For Flask-specific development:
```bash
# Run Flask without debug mode (recommended)
python run_app.py

# Run Flask with debug mode (LOCAL DEVELOPMENT ONLY - NEVER use in production!)
# WARNING: Debug mode is a security vulnerability - it exposes sensitive data
FLASK_DEBUG=true python run_app.py  # INSECURE - Use only for local debugging!
```

The Flask app will be available at `http://localhost:5001`

## Project Structure

```
comiccaster/
├── comiccaster/           # Main Python package
│   ├── base_scraper.py    # Abstract base class for all scrapers
│   ├── gocomics_scraper.py # GoComics HTTP scraper with JSON-LD parsing
│   ├── tinyview_scraper.py # TinyView Selenium-based scraper
│   ├── scraper_factory.py  # Factory pattern for scraper selection
│   ├── feed_generator.py   # RSS feed generation with multi-image support
│   ├── loader.py          # Comic configuration management
│   └── web_interface.py   # Flask web application
├── public/               # Static files served by Netlify
│   ├── index.html       # Main application page with tabbed interface
│   ├── feeds/           # Pre-generated RSS feed files
│   └── comics_list.json # Comic metadata with source information
├── functions/           # Netlify serverless functions
│   ├── generate-opml.js # OPML bundle generation
│   └── fetch-feed.js    # Feed preview functionality
├── scripts/             # Utility and update scripts
│   ├── update_feeds.py  # Daily feed update orchestrator
│   └── test_gocomics_regression.py # Regression testing
├── tests/               # Test suite
│   ├── test_base_scraper.py    # Base scraper tests
│   ├── test_tinyview_scraper.py # TinyView scraper tests
│   ├── test_multi_image_rss.py  # Multi-image RSS tests
│   └── test_scraper_factory.py  # Factory pattern tests
├── docs/                # Documentation
│   └── specifications/  # Project specifications and design docs
└── legacy_scripts/      # Historical scripts for reference
```

## Feed Updates

Feeds are automatically updated daily via GitHub Actions. The workflow:
1. Runs the enhanced update script to fetch latest comics using JSON-LD date matching
2. Ensures accurate detection of daily comics vs "best of" reruns
3. Commits updated feed files to the repository
4. Triggers a new Netlify deployment
5. **Validates feed freshness** using canary monitoring (new!)

### Recent Improvements (July 2025)

**TinyView Integration:**
- **New Platform**: Added support for 29 independent comics from TinyView.com
- **Multi-Strip Comics**: Full support for comics that publish multiple strips per day
- **Selenium Scraping**: Implemented Selenium WebDriver to handle TinyView's dynamic content
- **Smart Date Matching**: Advanced logic to extract comics from specific dates across complex URL structures
- **Description Extraction**: Captures artist commentary and descriptions when available

**Architectural Improvements:**
- **Scraper Factory Pattern**: Modular system for managing different comic sources
- **Base Scraper Class**: Standardized interface for all scrapers with shared functionality
- **Multi-Image RSS**: Enhanced feed generator supports comics with multiple images per entry
- **Source Field**: Each comic now has a granular source field (gocomics-daily, gocomics-political, tinyview)
- **Comprehensive Testing**: Added 100+ tests covering all new functionality

**Political Comics Integration:**
- **New Feature**: Added support for 63+ political editorial cartoons from GoComics
- **Tabbed Interface**: Separate tabs for daily comics and political cartoons for better organization
- **Smart Updates**: Comics are updated based on their publishing frequency (daily, weekly, irregular)
- **Content Warnings**: Political feeds include appropriate descriptions and content categories
- **Separate OPML Files**: Generate `daily-comics.opml` or `political-cartoons.opml` based on your preferences

### Latest Changes (October 2025)

**Title Format Consistency Fix (October 11, 2025):**
- **Problem**: Feed titles were being rewritten on every update, causing Git to see changes to ALL entries (not just new ones)
- **Root Cause**: `scrape_comic()` created titles without day-of-week ("Garfield - 2025-10-11"), but `feed_generator.create_entry()` added it ("Garfield - Fri 2025-10-11"), rewriting every title during feed generation
- **Solution**: Updated `scrape_comic()` to include day-of-week in titles, matching the `feed_generator` format
- **Result**: Git commits now only show actual new comic entries, not unnecessary rewrites of existing entries
- **Benefits**:
  - ✅ Cleaner Git commit history showing only real changes
  - ✅ Faster feed updates (no unnecessary processing of unchanged entries)
  - ✅ Easier to debug feed update issues
  - ✅ Reduced repository churn

**TLS Fingerprinting Breakthrough - Selenium Removed (October 9, 2025):**
- **Problem**: BunnyShield CDN was blocking HTTP requests in CI due to Python's TLS fingerprint detection, forcing 100% Selenium usage = 3+ hour runtimes with OOM failures
- **Solution**: Switched to `tls-client` library with Chrome 120 TLS fingerprint + full browser headers
- **Results**: **100% HTTP success rate at 0.25s per comic** = ~2 minutes total for 400+ comics (90x speedup!)
- **Selenium Removed**: After testing 407 comics, TLS client achieved 100% page fetch success - Selenium fallback completely removed for GoComics
- **Technical Details**:
  - Using `tls-client` Python library with `chrome_120` client identifier
  - Complete browser header suite (Accept, Accept-Language, Sec-Fetch-*, Brotli support)
  - Thread-safe global TLS session with proper locking
  - **No Selenium dependency** for GoComics (TinyView still uses it)
  - JSON-LD date matching remains primary scraping strategy
  - Comics without content for requested date properly return 404/empty (as expected)
- **Performance Comparison**:
  - Selenium-only approach: 8s per comic = **3+ hours total** (OOM failures in CI)
  - Python requests + headers: 60% success locally, 0% in CI (TLS fingerprint detected)
  - **tls-client only: 100% success, 0.25s per comic = ~2 minutes total** ✅
- **Benefits**:
  - ✅ 90x speedup compared to Selenium-only approach
  - ✅ Zero memory exhaustion in GitHub Actions
  - ✅ Reliable, fast updates that complete in ~2 minutes
  - ✅ Works perfectly in CI environments (datacenter IPs no longer blocked)
  - ✅ Maintains accurate date-based comic detection via JSON-LD
  - ✅ Simpler code with no browser management complexity
  - ✅ Comics that don't publish daily are properly skipped (not errors)

**Wrong Comics Bug Fix (October 9, 2025):**
- **Problem**: Feeds were showing strips from unrelated comics (e.g., Gilbert's dog comic in Brewster Rockit feed)
- **Root Cause**: Undated CSS selector fallbacks grabbed any comic image from GoComics pages without validating dates
- **Solution**: Removed all undated fallback methods - now ONLY uses JSON-LD with exact date matching
- **Result**: Better to skip a day than show the wrong comic
- **Benefits**:
  - ✅ Feeds now show correct comics or nothing (no wrong comics)
  - ✅ Maintains data integrity and user trust
  - ✅ Simpler, more maintainable code

**Previous BunnyShield Work (October 2025):**
- Initial attempts to bypass BunnyShield with browser headers, Selenium fallback, and browser pooling
- Successfully identified JSON-LD parsing as the correct approach
- Learned that Python requests library's TLS fingerprint was the real blocker
- See commit history for full evolution of the solution

### Previous Improvements (June 2025)

**Enhanced Comic Detection System:**
- **Problem Solved**: GoComics serves both current daily comics and historical "best of" reruns on the same page, making it difficult to distinguish which is the actual daily comic
- **Solution**: Implemented JSON-LD structured data parsing with date matching to accurately identify the comic for the specific requested date
- **Previous Issue**: Comics like "Pearls Before Swine" and "In the Bleachers" were showing old reruns instead of current daily strips
- **Technical Details**: 
  - Switched from unreliable CSS selector approaches to JSON-LD `ImageObject` parsing
  - Added date matching logic that finds comics with publication dates matching the requested date
  - Maintained HTTP-only approach for better performance and reliability in CI/CD environments
  - Increased parallelization to 8 workers for faster feed updates

**Benefits:**
- ✅ All 404+ comic feeds now show correct daily comics
- ✅ Reliable distinction between daily content and "best of" reruns  
- ✅ Improved performance with parallel processing
- ✅ Better error handling and logging
- ✅ GitHub Actions workflow optimized for stability

### Feed Health Monitoring (July 2025)

**Automated Feed Validation System:**
- **Problem Solved**: Feed generation bugs could go unnoticed for days, resulting in stale feeds
- **Solution**: Implemented canary monitoring using 15 reliable daily comics as health indicators
- **How it works**:
  - After each daily update, a validation script checks if canary feeds have entries within 3 days
  - If any canary feeds are stale, the system automatically creates a GitHub issue with details
  - Canary comics include: Garfield, Pearls Before Swine, Doonesbury, Calvin and Hobbes, and 11 others
- **Benefits**:
  - ✅ Proactive detection of feed update failures
  - ✅ Automated alerting via GitHub issues
  - ✅ Detailed diagnostics for troubleshooting
  - ✅ Prevents multi-day outages from going unnoticed

## Technical Components

- **Static Site**: Served by Netlify
- **Serverless Functions**: Handle OPML generation and feed previews
- **GitHub Actions**: Automate daily feed updates for both GoComics and TinyView
- **Python Scripts**: Generate and update RSS feeds
- **Scrapers**: 
  - GoComics scraper using HTTP requests with JSON-LD parsing
  - TinyView scraper using Selenium WebDriver for dynamic content

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/adamprime/comiccaster.git
cd comiccaster

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .  # Install package in development mode

# Install test dependencies
pip install pytest pytest-cov pytest-mock

# For TinyView development (requires Firefox)
# macOS
brew install --cask firefox

# Ubuntu
sudo apt-get install firefox firefox-geckodriver
```

### Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest -v --cov=comiccaster --cov-report=term-missing

# Run specific test category
pytest -v tests/test_tinyview_scraper.py
```

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive testing documentation.

### Adding New Comics

1. **For GoComics**: Add to appropriate JSON file in `public/`
2. **For TinyView**: Add to `public/tinyview_comics_list.json`
3. **Required fields**:
   ```json
   {
     "name": "Comic Name",
     "slug": "comic-slug",
     "url": "https://source.com/comic-slug",
     "source": "gocomics-daily|gocomics-political|tinyview"
   }
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Contribution Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`pytest -v`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Supported Comic Sources

### GoComics
- **Daily Comics**: Calvin and Hobbes, Garfield, Dilbert, and hundreds more
- **Political Cartoons**: Doonesbury, Non Sequitur, and other editorial comics
- **Update Frequency**: Checks last 10 days of comics
- **Scraping Method**: HTTP requests with JSON-LD parsing

### TinyView
- **Independent Comics**: 29 comics including ADHDinos, Fowl Language, Nick Anderson, Pedro X. Molina, and more
- **Multi-strip Support**: Handles comics that publish multiple strips per day
- **Update Frequency**: Checks last 15 days of comics (accommodates less frequent updates)
- **Comic Descriptions**: Extracts and includes artist commentary when available
- **Scraping Method**: Selenium WebDriver for dynamic content

## Acknowledgments

- Thanks to GoComics and TinyView for providing the comic content
- Built with Netlify Functions and GitHub Actions 
- Inspired by ComicsRSS.com