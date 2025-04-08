# ComicCaster

A Python-based RSS feed generator for GoComics that allows you to create personalized comic feeds.

## Features

- Generate individual RSS feeds for any comic on GoComics
- Create personalized combined feeds using OPML files
- Web interface for easy comic selection and feed generation
- Automatic daily updates via GitHub Actions
- Serverless deployment with Netlify
- Simple configuration system
- Secure token-based feed access

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
git remote add origin https://github.com/yourusername/comiccaster.git
git push -u origin main
```

3. Enable GitHub Actions in your repository settings

### Netlify Deployment

1. Sign up for a Netlify account at https://www.netlify.com/
2. Connect your GitHub repository to Netlify
3. Configure the build settings:
   - Build command: `npm install -g netlify-cli && netlify build`
   - Publish directory: `public`
4. Set up environment variables in Netlify:
   - `GITHUB_TOKEN`: A GitHub personal access token with repo access
5. Configure your custom domain in Netlify's domain settings

## Automatic Updates

The application uses GitHub Actions to automatically update comic feeds daily. The workflow:

1. Runs every day at 1 AM UTC
2. Updates all comic feeds
3. Cleans up old tokens (older than 7 days)
4. Commits and pushes changes automatically
5. Creates GitHub issues if updates fail

## Feed Generation

### Individual Feeds

Each comic has its own RSS feed accessible at:
```
https://yourdomain.com/.netlify/functions/individual-feed?comic=comic-slug
```

### Combined Feeds

Combined feeds are generated using OPML files. To create a combined feed:

1. Select your desired comics in the web interface
2. Download the generated OPML file
3. Use the OPML file with your preferred RSS reader

## Security

- Feeds are protected by token-based authentication
- Tokens expire after 7 days
- Old tokens are automatically cleaned up
- GitHub Actions uses secure tokens for authentication

## Making Your Own Instance Public

If you want to make your instance of this project public:

1. **Security First**:
   - Ensure no sensitive data is in the repository
   - Check `.gitignore` is properly configured
   - Remove any API keys or secrets
   - Verify environment variables are properly set

2. **Repository Setup**:
   - Add a LICENSE file (MIT License recommended)
   - Update README with your specific deployment details
   - Add contribution guidelines
   - Set up issue templates

3. **Documentation**:
   - Document any custom configurations
   - Add setup instructions for your specific instance
   - Include troubleshooting guides
   - Add contact information for support

4. **Maintenance**:
   - Set up automated dependency updates
   - Configure issue and PR templates
   - Add status badges
   - Set up project boards if needed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 