# TinyView Authentication Setup

This guide explains how to set up authenticated scraping for TinyView comics using cookie persistence.

## Overview

TinyView uses magic link authentication (passwordless login via email). Since we can't automate email checking, we use a cookie-based approach similar to Comics Kingdom:

1. **One-time Setup**: Login manually with magic link, save cookies
2. **Automated Scraping**: Reuse saved cookies for daily updates
3. **Periodic Re-auth**: Re-authenticate when cookies expire (~30 days)

## Quick Start

### 1. Set Your Email

Add your TinyView email to `.env`:

```bash
# TinyView Authentication
TINYVIEW_EMAIL=adam@tervort.org
TINYVIEW_COOKIE_FILE=data/tinyview_cookies.pkl
```

### 2. Run Setup Script

```bash
./SETUP_TINYVIEW_AUTH.sh
```

This will:
- Open a browser window
- Let you complete magic link login
- Save cookies for future use
- Test authentication
- Discover all comics you follow

### 3. Manual Setup (Alternative)

If the setup script doesn't work, you can run each step manually:

```bash
# Authenticate and save cookies
export TINYVIEW_EMAIL=adam@tervort.org
export TINYVIEW_COOKIE_FILE=data/tinyview_cookies.pkl
python3 tinyview_scraper_secure.py --show-browser

# Get notifications (recent updates)
python3 tinyview_scraper_secure.py --get-notifications

# Discover all followed comics
python3 tinyview_scraper_secure.py --discover-comics
```

## How It Works

### Magic Link Login Process

1. Script opens browser to tinyview.com
2. Fills in your email address
3. **You manually**: Click "Send magic link" button
4. **You manually**: Check email and click magic link
5. Browser automatically logs you in
6. Script detects login and saves cookies

### Cookie Persistence

```python
# First run: authenticate and save
authenticate_with_cookie_persistence(driver, config)
save_cookies(driver, 'data/tinyview_cookies.pkl')

# Subsequent runs: load cookies
load_cookies(driver, 'data/tinyview_cookies.pkl')
if is_authenticated(driver):
    # Ready to scrape!
```

### Cookie Lifespan

- Cookies typically last **30+ days**
- Script warns when cookies are old
- Re-authenticate when expired: `./SETUP_TINYVIEW_AUTH.sh`

## Features

### 1. Authenticated Scraping

Once authenticated, you can access:
- Full comic content (not just previews)
- Notifications page (recent updates from all followed comics)
- Your followed comics list
- Better scraping reliability

### 2. Notifications Page

The notifications page shows recent updates from all comics you follow:

```python
# Get recent notifications
python3 tinyview_scraper_secure.py --get-notifications
```

Output: `data/tinyview_notifications_TIMESTAMP.json`

```json
[
  {
    "comic_slug": "pedro-x-molina",
    "comic_name": "Pedro X Molina",
    "date": "2025/11/19",
    "title": "donald-trump-hosted-saudi",
    "url": "https://tinyview.com/pedro-x-molina/2025/11/19/donald-trump-hosted-saudi",
    "timestamp": "2h ago",
    "source": "tinyview"
  }
]
```

This is the **key to smart updates** - only scrape comics that have new content!

### 3. Comic Discovery

Automatically discover all comics you follow:

```bash
python3 tinyview_scraper_secure.py --discover-comics
```

Output: `data/tinyview_discovered_comics.json`

```json
[
  {
    "name": "Pedro X Molina",
    "slug": "pedro-x-molina",
    "url": "https://tinyview.com/pedro-x-molina",
    "source": "tinyview"
  }
]
```

Compare with `public/tinyview_comics_list.json` to find missing comics.

## Integration with Existing Scraper

The new authenticated scraper works alongside the existing `TinyviewScraper` class:

### Option 1: Update TinyviewScraper to accept cookies

```python
class TinyviewScraper(BaseScraper):
    def __init__(self, cookie_file=None):
        self.cookie_file = cookie_file
        
    def setup_driver(self):
        super().setup_driver()
        if self.cookie_file and Path(self.cookie_file).exists():
            load_cookies(self.driver, self.cookie_file)
```

### Option 2: Pre-authenticate driver before scraping

```python
# In update script
from tinyview_scraper_secure import authenticate_with_cookie_persistence, setup_driver

driver = setup_driver()
config = load_config_from_env()
if authenticate_with_cookie_persistence(driver, config):
    # Pass authenticated driver to scraper
    scraper = TinyviewScraper(driver=driver)
```

## Smart Update Strategy

With authentication + notifications, we can optimize updates:

### Current Approach (Blind Scraping)
- Scrape all 29 comics every run
- Most have no new content
- Wastes time and resources

### New Approach (Notification-Driven)
1. Get notifications (which comics updated recently)
2. Only scrape comics that appear in notifications
3. Fall back to periodic full scrapes for weekly/irregular comics

```python
# Pseudo-code for smart updates
notifications = get_tinyview_notifications()
comics_to_update = [n['comic_slug'] for n in notifications]

for comic in comics_to_update:
    scrape_comic(comic)
```

## Environment Variables

Add to `.env`:

```bash
# TinyView Authentication
TINYVIEW_EMAIL=your-email@example.com
TINYVIEW_COOKIE_FILE=data/tinyview_cookies.pkl
```

## Troubleshooting

### "Could not find email field"

The login page structure may have changed. Update the selectors in `login_with_magic_link()`:

```python
selectors = [
    (By.NAME, "email"),
    (By.ID, "email"),
    (By.CSS_SELECTOR, "input[type='email']"),
    # Add more as needed
]
```

### "Timeout waiting for login"

The script waits 5 minutes for you to complete the magic link flow. If you need more time:

```python
for i in range(120):  # Increase from 60 to 120 (10 minutes)
    time.sleep(5)
    if is_authenticated(driver):
        return True
```

### "Authentication check fails even when logged in"

Update the `is_authenticated()` function to check for different indicators:

```python
def is_authenticated(driver):
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Check for user-specific elements
    has_notifications = soup.find('a', href='/notifications')
    has_profile_menu = soup.find('button', {'aria-label': 'User menu'})
    
    return bool(has_notifications or has_profile_menu)
```

### Cookies Expired

Re-authenticate by running setup again:

```bash
./SETUP_TINYVIEW_AUTH.sh
```

Or force re-authentication:

```bash
python3 tinyview_scraper_secure.py --show-browser --force-reauth
```

## GitHub Actions / CI Setup

### 1. Create GitHub Secret

After authenticating locally, encode cookies:

```bash
base64 data/tinyview_cookies.pkl > tinyview_cookies_base64.txt
```

Add to GitHub Secrets as `TINYVIEW_COOKIES_BASE64`

### 2. Update Workflow

```yaml
- name: Setup TinyView Authentication
  run: |
    mkdir -p data
    echo "${{ secrets.TINYVIEW_COOKIES_BASE64 }}" | base64 -d > data/tinyview_cookies.pkl

- name: Update TinyView Feeds
  env:
    TINYVIEW_EMAIL: ${{ secrets.TINYVIEW_EMAIL }}
    TINYVIEW_COOKIE_FILE: data/tinyview_cookies.pkl
    CI: true
  run: python scripts/update_tinyview_feeds.py
```

### 3. Update Secret When Cookies Expire

Monitor for authentication failures in GitHub Actions, then:

1. Re-authenticate locally
2. Re-encode cookies
3. Update `TINYVIEW_COOKIES_BASE64` secret

## Security Notes

- Cookies are stored in `data/tinyview_cookies.pkl` (gitignored)
- Never commit cookies to git
- Email is in `.env` (also gitignored)
- GitHub Secret stores encrypted cookies for CI
- Cookies can only access your TinyView account (no other sites)

## Next Steps

After completing authentication setup:

1. **Update the TinyView scraper** to use authenticated sessions
2. **Implement notification-based updates** for efficiency
3. **Add comic discovery** to auto-detect new followed comics
4. **Test automated updates** with saved cookies
5. **Set up GitHub Actions** with cookie secret

See `scripts/update_tinyview_feeds_authenticated.py` (to be created) for the new update script.
