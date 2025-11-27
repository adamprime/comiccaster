# ComicCaster

ComicCaster is a web application that generates RSS feeds for comics from multiple sources including GoComics, TinyView, Comics Kingdom, and The Far Side. It provides a unified interface to subscribe to your favorite comics through RSS.

## Features

### Core Functionality
- **500+ Comics Available**: Access to comics from GoComics, Comics Kingdom, TinyView, and The Far Side
- **Multi-Source Architecture**: Unified interface for comics from different platforms
- **RSS Feed Generation**: Standard RSS 2.0 feeds compatible with all major feed readers
- **OPML Bundle Creation**: Generate custom bundles of comics for easy import into feed readers

### Advanced Features
- **Multi-Image RSS Support**: Full support for comics that publish multiple images/panels per day
- **Accurate Daily Comic Detection**: Distinguishes between current daily comics and "best of" reruns
- **Smart Update Scheduling**: Optimizes feed updates based on comic publishing patterns (daily, weekly, irregular)
- **Parallel Processing**: Efficient concurrent feed generation
- **Feed Health Monitoring**: Automated canary system detects and alerts on stale feeds

### User Interface
- **Tabbed Navigation**: Separate tabs for daily comics, political cartoons, and TinyView comics
- **Feed Preview**: Check comic content before subscribing
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Search and Filter**: Quickly find comics by name or category

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
│   ├── loader.py          # Comic configuration management
│   └── web_interface.py   # Flask web application
├── public/               # Static files served by Netlify
│   ├── index.html       # Main application page
│   ├── feeds/           # Pre-generated RSS feed files
│   └── comics_list.json # Comic metadata
├── functions/           # Netlify serverless functions
│   ├── generate-opml.js # OPML bundle generation
│   └── fetch-feed.js    # Feed preview functionality
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
5. Canary monitoring validates feed freshness

### Key Features

- **Multi-Source Support**: Comics from GoComics, Comics Kingdom, TinyView, and The Far Side
- **Accurate Detection**: Distinguishes current daily comics from reruns
- **Multi-Image Support**: Handles comics with multiple panels per day
- **Feed Health Monitoring**: Canary system alerts on stale feeds
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
- **Daily Comics**: Calvin and Hobbes, Garfield, and hundreds more
- **Political Cartoons**: Doonesbury, Non Sequitur, and other editorial comics

### Comics Kingdom
- **Classic and Modern Comics**: Zits, Beetle Bailey, Mutts, and more

### TinyView
- **Independent Comics**: ADHDinos, Fowl Language, and more
- **Multi-strip Support**: Handles comics that publish multiple strips per day

### The Far Side
- **Daily Far Side**: Gary Larson's classic comic

## Acknowledgments

- Thanks to GoComics, Comics Kingdom, TinyView, and The Far Side for providing comic content
- Built with Netlify Functions and GitHub Actions 
- Inspired by ComicsRSS.com