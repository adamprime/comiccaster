# ComicCaster

[![Tests](https://github.com/adamprime/comiccaster/actions/workflows/tests.yml/badge.svg)](https://github.com/adamprime/comiccaster/actions/workflows/tests.yml)
[![Update Feeds](https://github.com/adamprime/comiccaster/actions/workflows/update-feeds.yml/badge.svg)](https://github.com/adamprime/comiccaster/actions/workflows/update-feeds.yml)

A Python-based RSS feed generator for GoComics that allows you to subscribe to individual comic feeds or create personalized collections using OPML files.

## Features

- Generate individual RSS feeds for any comic on GoComics
- Create OPML files for easy import of multiple feeds into your RSS reader
- Dark mode user interface
- Simple comic search and selection
- Automatic daily updates via GitHub Actions
- Serverless deployment options with Netlify Functions
- Self-hosted option with Python Flask

## How It Works

### Individual Comic Feeds
ComicCaster scrapes GoComics daily to create individual RSS feeds for each comic. Each feed contains:
- The comic image
- Title and description
- Link to the original page
- Publication date

### OPML Generation
Instead of creating combined feeds, ComicCaster now generates OPML files:
1. Select your favorite comics in the web interface
2. Click "Generate OPML File" 
3. Import the OPML file into your RSS reader
4. Your reader will subscribe to each individual feed automatically

### Daily Updates
A GitHub Actions workflow runs daily to:
- Scrape the latest comic strips from GoComics
- Update individual comic feeds
- Clean up old tokens (legacy function)
- Commit the updated feed files to the repository
- Push changes to trigger automatic deployment

### Feed Storage
ComicCaster now keeps feed XML files in the Git repository:
- Ensures feeds are immediately available after deployment
- Provides version history of feed changes
- Makes debugging easier with transparent feed content
- Increases reliability of the netlify deployment

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/comiccaster.git
cd comiccaster
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
```
Then edit `.env` with your configuration values.

## Project Structure

```
comiccaster/
├── .github/             # GitHub configuration
│   └── workflows/       # GitHub Actions workflows
│       └── update-feeds.yml # Daily feed update workflow
├── comiccaster/         # Main package directory
│   ├── __init__.py
│   ├── loader.py        # Comics list loader
│   ├── scraper.py       # Comic scraper module
│   ├── feed_generator.py # RSS feed generator
│   ├── web_interface.py # Flask web interface
│   └── templates/       # HTML templates
│       ├── base.html    # Base template with styling
│       └── index.html   # Main page template
├── functions/           # Netlify serverless functions
│   ├── individual-feed.js # Function to serve individual feeds
│   ├── generate-token.js # Function to generate OPML
│   └── package.json     # Node.js dependencies
├── scripts/             # Utility scripts
│   └── update_feeds.py  # Feed update script
├── feeds/               # Generated RSS feeds (*.xml)
├── comics_list.json     # List of available comics
└── README.md            # This documentation
```

## Running Locally

To run the web interface locally:

```bash
export FLASK_APP=comiccaster.web_interface
export FLASK_ENV=development
flask run --port=5001
```

The site will be available at http://localhost:5001

## Feed Update Script

The `scripts/update_feeds.py` script handles updating all feeds:

```bash
python scripts/update_feeds.py
```

This script:
1. Loads the comic list from `comics_list.json`
2. Scrapes the latest comic for each entry
3. Updates each comic's RSS feed
4. Reports success/failure statistics

## Deployment Options

### Self-Hosted Flask

1. Set up a server with Python installed
2. Clone the repository
3. Install dependencies
4. Configure a production WSGI server (e.g., Gunicorn)
5. Set up a reverse proxy (e.g., Nginx)
6. Configure a scheduled task to run `update_feeds.py` daily

### Netlify Deployment

1. Connect your GitHub repository to Netlify
2. Configure build settings:
   - Build command: `npm install -g netlify-cli && netlify build`
   - Publish directory: `public`
3. Set up environment variables in Netlify
4. Configure your custom domain

## Technical Components

- **Backend**: Python with Flask for web serving
- **Feed Generation**: Uses `feedgen` library for RSS creation
- **Web Scraping**: BeautifulSoup for parsing with requests/Selenium for fetching
- **Frontend**: HTML/CSS with JavaScript for interactivity
- **Deployment**: GitHub Actions for automated updates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 