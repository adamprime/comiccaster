# ComicCaster

ComicCaster is a web application that generates RSS feeds for comics from GoComics.com. It allows you to subscribe to individual comics or create custom bundles of multiple comics using OPML files.

## Features

- Individual RSS feeds for 400+ daily comics and 60+ political cartoons from GoComics
- **Accurate daily comic detection** - distinguishes between current daily comics and "best of" reruns
- **Tabbed interface** - separate browsing for daily comics and political editorial cartoons
- **Smart update scheduling** - optimizes feed updates based on comic publishing patterns
- **Political comic support** - dedicated feeds for editorial cartoons with appropriate content descriptions
- Feed preview functionality to check comic content before subscribing
- OPML file generation for custom comic bundles (separate files for daily comics and political cartoons)
- Modern, responsive web interface with intuitive tab navigation
- Fast and efficient serverless deployment
- Daily feed updates via GitHub Actions with enhanced scraping reliability

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

# Run Flask with debug mode (development only - NEVER use in production)
FLASK_DEBUG=true python run_app.py
```

The Flask app will be available at `http://localhost:5001`

## Project Structure

```
comiccaster/
├── public/              # Static files served by Netlify
│   ├── index.html      # Main application page
│   ├── preview.html    # Feed preview page
│   ├── feeds/          # Generated RSS feed files
│   └── comics_list.json # List of available comics
├── functions/          # Netlify serverless functions
│   ├── generate-opml.js # OPML generation function
│   └── fetch-feed.js   # Feed preview function
├── scripts/           # Utility scripts
│   └── update_feeds.py # Daily feed update script
└── netlify.toml      # Netlify configuration
```

## Feed Updates

Feeds are automatically updated daily via GitHub Actions. The workflow:
1. Runs the enhanced update script to fetch latest comics using JSON-LD date matching
2. Ensures accurate detection of daily comics vs "best of" reruns
3. Commits updated feed files to the repository
4. Triggers a new Netlify deployment
5. **Validates feed freshness** using canary monitoring (new!)

### Recent Improvements (July 2025)

**Political Comics Integration:**
- **New Feature**: Added support for 63+ political editorial cartoons from GoComics
- **Tabbed Interface**: Separate tabs for daily comics and political cartoons for better organization
- **Smart Updates**: Comics are updated based on their publishing frequency (daily, weekly, irregular)
- **Content Warnings**: Political feeds include appropriate descriptions and content categories
- **Separate OPML Files**: Generate `daily-comics.opml` or `political-cartoons.opml` based on your preferences

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
- **GitHub Actions**: Automate daily feed updates
- **Python Scripts**: Generate and update RSS feeds

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to GoComics for providing the comic content
- Built with Netlify Functions and GitHub Actions 
- Inspired by ComicsRSS.com