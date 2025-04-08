# RSS Comics

A Python-based RSS feed generator for GoComics that allows you to create personalized comic feeds.

## Features

- Generate individual RSS feeds for any comic on GoComics
- Create personalized combined feeds of your favorite comics
- Web interface for easy comic selection and feed generation
- Automatic daily updates via GitHub Actions
- Serverless deployment with Netlify
- Simple configuration system

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/rss-comics.git
cd rss-comics
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
rss-comics/
├── .github/             # GitHub configuration
│   └── workflows/       # GitHub Actions workflows
│       └── update-feeds.yml # Daily feed update workflow
├── comiccaster/         # Main package directory
│   ├── __init__.py
│   ├── loader.py       # Comics A-to-Z loader
│   ├── scraper.py      # Comic scraper module
│   ├── feed_generator.py # RSS feed generator
│   ├── feed_aggregator.py # Feed aggregator
│   └── templates/      # HTML templates
├── config/             # Configuration files
│   └── config.json    # User configuration
├── feeds/             # Generated RSS feeds
├── functions/         # Netlify serverless functions
│   ├── individual-feed.js # Function to serve individual feeds
│   ├── combined-feed.js # Function to generate combined feeds
│   ├── generate-token.js # Function to generate tokens
│   └── package.json   # Node.js dependencies
├── public/            # Static web files
│   ├── index.html    # Main page
│   ├── feed-generated.html # Feed generated page
│   ├── css/          # Stylesheets
│   │   └── styles.css # Main stylesheet
│   └── js/           # JavaScript files
│       └── app.js    # Main JavaScript
├── scripts/          # Utility scripts
│   └── update_feeds.py # Feed update script
├── tokens/           # User token storage
│   └── README.md     # Token directory documentation
├── requirements.txt  # Python dependencies
├── netlify.toml      # Netlify configuration
├── comics_list.json  # List of available comics
└── README.md         # This file
```

## Deployment

### GitHub Setup

1. Create a new GitHub repository
2. Push your code to the repository:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/rss-comics.git
git push -u origin main
```

3. Enable GitHub Actions in your repository settings

### Netlify Deployment

1. Sign up for a Netlify account at https://www.netlify.com/
2. Connect your GitHub repository to Netlify
3. Configure the build settings:
   - Build command: `npm install -g netlify-cli && netlify build`
   - Publish directory: `public`
   - Functions directory: `functions`

4. Deploy your site

### Custom Domain (Optional)

1. In the Netlify dashboard, go to "Domain settings"
2. Click "Add custom domain"
3. Follow the instructions to configure your domain

## Usage

### Web Interface

1. Visit your deployed Netlify site
2. Browse the available comics
3. Select your favorite comics
4. Generate a personalized feed
5. Subscribe to the generated feed URL in your RSS reader

### Individual Feeds

Individual comic feeds are available at:
```
https://your-site-name.netlify.app/rss/comic-slug
```

### Combined Feeds

Combined feeds are available at:
```
https://your-site-name.netlify.app/.netlify/functions/combined-feed?token=YOUR_TOKEN
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 