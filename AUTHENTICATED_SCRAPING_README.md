# Authenticated Scraping (For Maintainers)

## Overview

ComicCaster supports authenticated access for subscribers to maximize reliability and performance.

## Setup

### Required Environment Variables

For local development, create a `.env` file (see `.env.example` for template):

```bash
GOCOMICS_EMAIL=your-email@example.com
GOCOMICS_PASSWORD=your-password
CUSTOM_PAGE_1=your-custom-page-url
CUSTOM_PAGE_2=your-custom-page-url
# ... etc
```

### GitHub Actions Setup

For automated deployments, configure these secrets in your repository:
- `GOCOMICS_EMAIL`
- `GOCOMICS_PASSWORD`
- `CUSTOM_PAGE_1` through `CUSTOM_PAGE_6`

See `.env.example` for the complete list.

## Usage

Run the secure scraper:

```bash
# Ensure environment variables are set first
python authenticated_scraper_secure.py --date 2024-11-12
```

The scraper will:
1. Authenticate using provided credentials
2. Extract comics from configured sources
3. Save results to JSON for feed generation

## Security Notes

- **Never commit** `.env` files or credentials to the repository
- All sensitive configuration is loaded from environment variables
- Cookies are not persisted - fresh authentication each run
- GitHub Secrets are encrypted and never visible in logs

## Integration

This authenticated scraper is designed to integrate with the existing feed generation pipeline. It outputs standardized JSON that can be consumed by `feed_generator.py`.

For questions or setup assistance, refer to `.env.example` and the inline documentation in `authenticated_scraper_secure.py`.
