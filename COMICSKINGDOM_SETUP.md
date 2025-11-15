# Comics Kingdom Setup Guide

## Overview

The Comics Kingdom scraper uses **cookie persistence** to avoid solving reCAPTCHA daily. You only need to authenticate once every 60-90 days.

## Initial Setup (One-Time)

### 1. Set Environment Variables

Add to your `.env` file:

```bash
# Comics Kingdom Credentials
COMICSKINGDOM_USERNAME=your-email@example.com
COMICSKINGDOM_PASSWORD=your-password-here
COMICSKINGDOM_COOKIE_FILE=data/comicskingdom_cookies.pkl
```

### 2. Run Initial Authentication

```bash
# Set up your environment variables first
source .env  # Or however you load env vars

# Run the re-authentication script
python3 scripts/reauth_comicskingdom.py
```

This will:
1. Open a browser window
2. Navigate to Comics Kingdom login
3. Fill in your credentials
4. **Wait for you to solve reCAPTCHA and click "Log in"**
5. Save cookies to `data/comicskingdom_cookies.pkl`

### 3. Test the Scraper

```bash
# This should work without any manual intervention now!
python3 comicskingdom_scraper_secure.py --show-browser

# Check the output
cat data/comicskingdom_*.json
```

## Daily Automated Use

Once authenticated, the scraper runs automatically:

```bash
# No reCAPTCHA needed! Uses saved cookies
python3 comicskingdom_scraper_secure.py

# Specify a date
python3 comicskingdom_scraper_secure.py --date 2025-11-14

# Force re-authentication if needed
python3 comicskingdom_scraper_secure.py --force-reauth --show-browser
```

## Re-Authentication (Every ~60 Days)

When cookies expire, you'll see:
```
⚠️  Saved cookies are expired or invalid
🔐 Manual login required
```

### Option 1: Use the Re-Auth Script (Recommended)

```bash
python3 scripts/reauth_comicskingdom.py
```

### Option 2: Force Re-Auth in Main Scraper

```bash
python3 comicskingdom_scraper_secure.py --force-reauth --show-browser
```

## Setting Up Calendar Reminder

### Option 1: Calendar Event

Add a recurring calendar event:
- **Title:** Re-authenticate Comics Kingdom
- **Frequency:** Every 6 weeks
- **Description:** Run `python3 scripts/reauth_comicskingdom.py`

### Option 2: Cron Job Alert

Add to your crontab:

```bash
# Check cookie age and alert if > 50 days old
0 9 * * * /path/to/check_ck_cookies.sh
```

Create `check_ck_cookies.sh`:

```bash
#!/bin/bash
COOKIE_FILE="/path/to/data/comicskingdom_cookies.pkl"

if [ -f "$COOKIE_FILE" ]; then
    AGE_DAYS=$(( ($(date +%s) - $(stat -f %m "$COOKIE_FILE")) / 86400 ))
    
    if [ $AGE_DAYS -gt 50 ]; then
        echo "⚠️  Comics Kingdom cookies are $AGE_DAYS days old"
        echo "Please re-authenticate soon: python3 scripts/reauth_comicskingdom.py"
        # Optional: send email/Slack notification
    fi
fi
```

### Option 3: GitHub Issue Alert

The scraper can automatically create a GitHub issue when cookies expire (future enhancement).

## GitHub Actions Setup

### 1. Add Secrets

Go to: Settings → Secrets and variables → Actions

Add these secrets:
- `COMICSKINGDOM_USERNAME` - your email
- `COMICSKINGDOM_PASSWORD` - your password
- `COMICSKINGDOM_COOKIES` - content of `data/comicskingdom_cookies.pkl` (base64 encoded)

### 2. Encode Cookies for GitHub Secrets

```bash
# After running reauth script locally:
base64 data/comicskingdom_cookies.pkl | pbcopy  # macOS
# Or
base64 data/comicskingdom_cookies.pkl > cookies_base64.txt  # Linux
```

Paste the base64 string into GitHub Secret `COMICSKINGDOM_COOKIES`

### 3. GitHub Workflow

The workflow will:
1. Decode cookies from secret
2. Run scraper (no manual intervention!)
3. Generate feeds
4. Create GitHub issue if authentication fails

### When to Update GitHub Secret

Every 60 days after re-authentication:

```bash
# 1. Re-authenticate locally
python3 scripts/reauth_comicskingdom.py

# 2. Encode new cookies
base64 data/comicskingdom_cookies.pkl | pbcopy

# 3. Update GitHub Secret: COMICSKINGDOM_COOKIES
#    (Go to repo Settings → Secrets → Actions)
```

## Troubleshooting

### Cookies Expired

**Symptom:**
```
⚠️  Saved cookies are expired or invalid
```

**Solution:**
```bash
python3 scripts/reauth_comicskingdom.py
```

### reCAPTCHA Not Appearing

**Symptom:** Login button stays disabled

**Solution:** 
- Make sure you're filling in BOTH username and password
- Try with `--show-browser` to see the page
- Check that credentials are correct

### No Comics Extracted

**Symptom:**
```
⚠️  No comics extracted
```

**Possible causes:**
1. Not logged in (check authentication)
2. No comics in favorites (add some at comicskingdom.com/favorites)
3. Page didn't load fully (increase wait times)

### Browser Not Found

**Symptom:**
```
selenium.common.exceptions.WebDriverException: chrome not found
```

**Solution:**
```bash
# Install Chrome
# macOS: brew install --cask google-chrome
# Ubuntu: sudo apt-get install google-chrome-stable

# Or use existing chromedriver
export PATH=$PATH:/path/to/chromedriver
```

## File Structure

```
data/
  └── comicskingdom_cookies.pkl        # Saved authentication cookies
  └── comicskingdom_YYYY-MM-DD.json    # Scraped comic data

scripts/
  └── reauth_comicskingdom.py          # Re-authentication helper

comicskingdom_scraper_secure.py        # Main scraper
```

## Security Notes

- ✅ Cookie files are in `.gitignore` (never commit!)
- ✅ Credentials loaded from environment variables
- ✅ Cookies stored locally in `data/` directory
- ✅ GitHub Secrets encrypted and never logged
- ⚠️  Don't share cookie files (they're authentication tokens)

## Next Steps

1. ✅ Initial authentication complete
2. ⏭️  Test scraper with `--show-browser`
3. ⏭️  Set up calendar reminder (6 weeks)
4. ⏭️  Add GitHub secrets for automated runs
5. ⏭️  Integrate into feed generation workflow
