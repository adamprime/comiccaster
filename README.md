# ComicCaster

ComicCaster is a web application that generates RSS feeds for comics from multiple sources: GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, and Mr. Boffo. It provides a unified interface to subscribe to your favorite comics through RSS.

## Features

### Core Functionality
- **500+ Comics Available**: Access to comics from GoComics, Comics Kingdom, TinyView, The Far Side, and first-party webcomic RSS feeds
- **Multi-Source Architecture**: Unified interface for comics from different platforms
- **RSS Feed Generation**: Standard RSS 2.0 feeds compatible with all major feed readers
- **OPML Bundle Creation**: Generate custom bundles of comics for easy import into feed readers

### Advanced Features
- **Multi-Image RSS Support**: Full support for comics that publish multiple images/panels per day
- **Accurate Daily Comic Detection**: Distinguishes between current daily comics and "best of" reruns
- **Smart Update Scheduling**: Optimizes feed updates based on comic publishing patterns (daily, weekly, irregular)
- **Parallel Processing**: Efficient concurrent feed generation
- **Pipeline Failure Alerting**: A failed scrape opens a GitHub issue that comments on recurrence and closes itself on recovery

### User Interface
- **Tabbed Navigation**: Separate tabs for daily comics, political cartoons, and TinyView comics
- **External RSS Directory**: Browse first-party RSS feeds for independent webcomics alongside ComicCaster-generated feeds
- **Feed Preview**: Check comic content before subscribing
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Search and Filter**: Quickly find comics by name or category

### For AI Agents and Developers
- **Machine-Readable Catalog**: [`/catalog.json`](https://comiccaster.xyz/catalog.json) lists every comic with one schema (name, author, source, category, language, feed URL, last update)
- **`llms.txt`**: [`/llms.txt`](https://comiccaster.xyz/llms.txt) explains the catalog, feed URL patterns and OPML generation for agents
- **Cross-Origin Access**: Feeds and the catalog send `Access-Control-Allow-Origin: *`, so browser-based tools can fetch them directly
- **Strip Images as Data**: Feed items name their strip images in a `comiccaster:images` element, so a tool can get them without parsing the description HTML. A feed picks this up the next time it publishes a strip
- **OPML from a Link**: [`/.netlify/functions/generate-opml?type=daily&comics=peanuts,pickles`](https://comiccaster.xyz/.netlify/functions/generate-opml?type=daily&comics=peanuts,pickles) downloads an OPML bundle any feed reader can import, one category per link

### Technical Features
- **Modular Architecture**: Extensible system supporting multiple comic sources
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
│   ├── feed_generator.py   # RSS feed generation
│   ├── loader.py          # Reads comic lists for the Flask app
│   └── web_interface.py   # Flask web application
├── public/               # Static files served by Netlify
│   ├── index.html       # Main application page
│   ├── feeds/           # Pre-generated RSS feed files
│   └── comics_list.json # Comic metadata
├── functions/           # Netlify serverless functions
│   ├── generate-opml.js # OPML bundle generation
│   └── fetch-feed.js    # Feed preview (allowlisted: own feeds + listed external feeds)
├── scripts/             # Utility and update scripts
├── tests/               # Test suite
└── docs/                # Documentation
```

## Feed Updates

Feeds are updated daily and committed to the repository. The workflow:
1. Runs update scripts to fetch latest comics from each source
2. Detects and includes only current daily comics (not reruns)
3. Commits updated feed files to the repository
4. Netlify automatically deploys when changes are pushed
5. Failures open a GitHub issue; a scheduled heartbeat catches a run that never happened at all

A second pass re-scrapes GoComics later in the day to pick up political and editorial
cartoonists who publish after the overnight window. The Far Side's Daily Dose is retried
every 30 minutes through the morning, because the site publishes it at an unpredictable hour.

### Key Features

- **Multi-Source Support**: Comics from GoComics, Comics Kingdom, TinyView, The Far Side, The New Yorker, Creators Syndicate, and Mr. Boffo
- **Accurate Detection**: Distinguishes current daily comics from reruns
- **Multi-Image Support**: Handles comics with multiple panels per day
- **Failure Alerting**: A failing source opens a GitHub issue and closes it automatically once the source recovers
- **Resilient Updates**: Graceful handling of missing comics and site changes

## Technical Components

- **Static Site**: Served by Netlify
- **Serverless Functions**: Handle OPML generation and feed previews
- **Python Scripts**: Generate and update RSS feeds

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

Each comic is an entry in one of the lists in `public/`. Every entry has `name`, `slug`, `url` and usually `author`; the `source` field says which scraper owns it.

| Source | List | `source` | Also needed |
|---|---|---|---|
| GoComics | `comics_list.json`, or `political_comics_list.json` for editorial cartoons | none | Add the comic to the GoComics account's favorites. The scraper reads the favorites pages, not the list. |
| Comics Kingdom | `comics_list.json` or `political_comics_list.json` | `"comicskingdom"` | `source_slug` when the slug differs from Comics Kingdom's |
| Creators Syndicate | `comics_list.json` | `"creators"` | `source_slug` (Creators' own slug) |
| TinyView | `tinyview_comics_list.json` | `"tinyview"` | |
| External RSS | `external_comics_list.json` | `"external-rss"` | `feed_url`. The list is curated: see [what qualifies](CONTRIBUTING.md#suggesting-an-external-rss-feed) |

The Far Side, The New Yorker and Mr. Boffo are fixed feeds with nothing to add. `spanish_comics_list.json` only drives the Spanish tab. A Spanish comic still needs its entry in its source's list (see `docs/solutions/ui-bugs/spanish-ui-filter-missing-comics-source-list-mismatch.md`).

A slug is a feed's identity (`public/feeds/<slug>.xml`), so it must not already belong to another source; `tests/test_catalog_source_integrity.py` checks this. After editing a list, rebuild the catalog and run the tests:

```bash
python scripts/generate_catalog.py
pytest -v
```

Adding a new *source*, rather than a comic, means a scraper and a generator. See `AGENTS.md` and `CLAUDE.md`.

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
- **Daily Comics**: Calvin and Hobbes, Garfield, and hundreds more
- **Political Cartoons**: Doonesbury, Non Sequitur, and other editorial comics

### Comics Kingdom
- **Classic and Modern Comics**: Zits, Beetle Bailey, Mutts, and more

### TinyView
- **Independent Comics**: ADHDinos, Fowl Language, and more
- **Multi-strip Support**: Handles comics that publish multiple strips per day

### The Far Side
- **Daily Far Side**: Gary Larson's classic comic

### External RSS Feeds
- **First-party feeds**: Popular independent webcomics that publish their own RSS feeds, such as xkcd and Poorly Drawn Lines
- **No scraping required**: ComicCaster links directly to the publisher's RSS feed
- **Suggesting one**: the list is curated; see [what qualifies](CONTRIBUTING.md#suggesting-an-external-rss-feed)

## Acknowledgments

- Thanks to GoComics, Comics Kingdom, TinyView, and The Far Side for providing comic content
- Built with Netlify Functions and GitHub Actions 
- Inspired by ComicsRSS.com
