# ComicCaster

ComicCaster is a web application that generates RSS feeds for comics from GoComics.com. It allows you to subscribe to individual comics or create custom bundles of multiple comics using OPML files.

## Features

- Individual RSS feeds for hundreds of comics from GoComics
- Feed preview functionality to check comic content before subscribing
- OPML file generation for custom comic bundles
- Modern, responsive web interface
- Fast and efficient serverless deployment
- Daily feed updates via GitHub Actions

## Quick Start

Visit [ComicCaster](https://comiccaster.xyz) to:
1. Browse available comics and preview their feeds
2. Subscribe to individual comics using their RSS feed URLs
3. Create custom bundles by selecting multiple comics and generating an OPML file
4. Import the OPML file into your favorite RSS reader

## Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/comiccaster.git
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
1. Runs the update script to fetch latest comics
2. Commits updated feed files to the repository
3. Triggers a new Netlify deployment

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