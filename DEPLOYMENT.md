# Deployment Guide

This guide provides detailed instructions for deploying ComicCaster to production.

## Prerequisites

- A GitHub account
- A server for hosting (Flask deployment) or a Netlify account (serverless deployment)
- Python 3.8 or higher
- Node.js 14 or higher (for Netlify functions)

## Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/comiccaster.git
cd comiccaster
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the development server:
```bash
export FLASK_APP=comiccaster.web_interface
export FLASK_ENV=development
flask run --port=5001
```

## Deployment Options

ComicCaster can be deployed either as a self-hosted Flask application or as a serverless application using Netlify Functions.

### Self-Hosted Flask Deployment

1. Set up a server with Python installed
2. Clone the repository and install dependencies
3. Configure a production WSGI server:

```bash
# Install Gunicorn
pip install gunicorn

# Run the application
gunicorn -w 4 'comiccaster.web_interface:app' -b 0.0.0.0:5000
```

4. Set up a reverse proxy (Nginx example):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /feeds/ {
        alias /path/to/comiccaster/feeds/;
        expires 1h;
    }
}
```

5. Set up a scheduled task for daily feed updates:

```bash
# Add to crontab
0 1 * * * cd /path/to/comiccaster && /path/to/python/bin/python scripts/update_feeds.py >> /var/log/comiccaster.log 2>&1
```

### Netlify Deployment

1. Create a new site on Netlify:
   - Connect your GitHub repository
   - Configure build settings:
     - Build command: `npm install -g netlify-cli && netlify build`
     - Publish directory: `public`

2. Configure Netlify Functions:
   - The functions are defined in the `functions` directory
   - The `netlify.toml` file already includes the necessary configuration
   - Functions automatically handle feed serving and OPML generation

3. Set up a GitHub Action for daily feed updates:
   - The workflow is defined in `.github/workflows/update-feeds.yml`
   - No additional configuration is needed
   - The action runs at 1 AM UTC daily

## Environment Variables

### Flask Deployment
- `FLASK_APP`: Set to `comiccaster.web_interface`
- `FLASK_ENV`: Set to `production` for deployment
- `SECRET_KEY`: A secure random string for session management

### Netlify Deployment
- `URL`: Your site's base URL (e.g., `https://comiccaster.xyz`)

## Feed Update Script

The feed update script (`scripts/update_feeds.py`) is responsible for:

1. Loading the comic list from `comics_list.json`
2. Scraping the latest comic for each comic
3. Updating the individual RSS feeds
4. Cleaning up legacy tokens (for backward compatibility)

For GitHub Actions deployment, this script is run automatically. For self-hosted deployment, set up a cron job to run it daily.

## Directory Structure

Important directories:

- `comiccaster/`: Core Python package
- `feeds/`: Generated RSS feed XML files
- `functions/`: Netlify serverless functions
- `scripts/`: Utility scripts including feed updater

## OPML Generation Feature

The OPML generation feature has replaced the previous combined feed approach. This simplifies deployment by:

1. Eliminating the need for server-side token storage
2. Removing the feed aggregation processing requirements
3. Improving performance by delegating feed handling to users' RSS readers

See `opml-generation.md` for detailed documentation on this feature.

## Maintenance Tasks

### Regular Updates

- Keep Python dependencies updated
- Monitor GitHub Actions runs for feed update failures
- Check server or Netlify logs for errors

### Troubleshooting Common Issues

1. **Missing Feeds**: 
   - Check if the comic is still available on GoComics
   - Check if the scraper is working properly
   - Verify that the feed directory is writable

2. **Scraper Failures**:
   - GoComics might have changed their HTML structure
   - Update the scraper logic in `comiccaster/scraper.py`
   - Check for rate limiting issues

3. **Performance Issues**:
   - The OPML generation is very lightweight
   - Individual feed serving should be efficient
   - Consider adding caching headers for feed files

## Security Considerations

1. **Server Protection**:
   - Keep your server and dependencies updated
   - Use HTTPS for all traffic
   - Implement rate limiting if needed

2. **No User Data**:
   - The application doesn't store user selections
   - No personal data is collected
   - No authentication is required

The simplified architecture with OPML generation reduces security concerns since there's no permanent storage of user selections.

## Monitoring

For a production deployment, consider setting up:

1. **Uptime Monitoring**:
   - Use a service like UptimeRobot to monitor your website
   - Set up alerts for downtime

2. **Log Monitoring**:
   - Check feed update logs regularly
   - Monitor web server logs for errors

3. **GitHub Actions**:
   - Monitor the daily feed update workflow
   - Set up notifications for workflow failures

---

This deployment guide covers the basics of deploying ComicCaster. The application is designed to be simple to deploy and maintain, with minimal server-side requirements. 