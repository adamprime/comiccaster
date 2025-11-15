# Local Comics Kingdom Automation

This document explains the hybrid automation setup for ComicCaster, where Comics Kingdom scraping happens locally and GoComics scraping happens in GitHub Actions.

## Architecture

```
┌─────────────────────────────────────┐
│   YOUR MAC (12:30 AM daily)         │
│                                      │
│  1. Scrape Comics Kingdom            │
│  2. Save to data/ directory          │
│  3. Git commit + push                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   GITHUB ACTIONS (9 AM UTC = 1-2AM) │
│                                      │
│  1. Scrape GoComics                  │
│  2. Read Comics Kingdom data         │
│  3. Generate ALL feeds               │
│  4. Commit + push feeds              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   NETLIFY (Auto-deploy)              │
│                                      │
│  Deploy updated feeds                │
└─────────────────────────────────────┘
```

## Why This Approach?

- **Comics Kingdom**: Works perfectly on Mac (authentication, reCAPTCHA), struggles in CI
- **GoComics**: Works perfectly in GitHub Actions (fast, reliable, no auth issues)
- **No Server Costs**: Uses existing infrastructure (your Mac + GitHub Actions)
- **Automated**: Runs daily without manual intervention once set up

## Setup

### 1. Install Local Automation

```bash
# Make sure you're in the repository directory
cd /path/to/rss-comics

# Install the launchd agent (runs daily at 12:30 AM)
./scripts/install_local_automation.sh
```

This will:
- Copy the launchd plist to `~/Library/LaunchAgents/`
- Load the agent so it runs daily
- Create log directories

### 2. Verify Environment Variables

Make sure you have a `.env` file in the repository root with:

```bash
COMICSKINGDOM_USERNAME="your_username"
COMICSKINGDOM_PASSWORD="your_password"
COMICSKINGDOM_COOKIE_FILE="/path/to/rss-comics/data/comicskingdom_cookies.pkl"
```

### 3. Test the Local Script

Before relying on automation, test manually:

```bash
./scripts/local_comicskingdom_update.sh
```

This should:
1. Scrape Comics Kingdom
2. Save data to `data/comicskingdom_YYYY-MM-DD.json`
3. Commit and push to GitHub
4. Trigger GitHub Actions automatically

### 4. Verify GitHub Actions

After the local script runs and pushes, GitHub Actions should:
1. Automatically trigger (webhook from your push)
2. Scrape GoComics
3. Find your Comics Kingdom data
4. Generate all feeds
5. Deploy to Netlify

## Daily Workflow

Once set up, the automation runs automatically:

**12:30 AM** (your Mac):
- Local script wakes up
- Scrapes Comics Kingdom
- Commits and pushes data

**~1:00 AM** (GitHub Actions):
- Triggered by your push OR scheduled run at 9 AM UTC
- Scrapes GoComics  
- Generates all feeds (GoComics + Comics Kingdom)
- Commits and pushes feeds

**~1:05 AM** (Netlify):
- Triggered by GitHub Actions push
- Deploys updated feeds
- Live at comiccaster.netlify.app

## Monitoring

### Check Local Automation Status

```bash
# See if agent is loaded
launchctl list | grep comicskingdom

# View recent logs
tail -50 ~/coding/rss-comics/logs/comicskingdom_local.log

# View launchd logs
tail -50 ~/coding/rss-comics/logs/comicskingdom_launchd.log
```

### Manually Trigger Local Script

```bash
cd ~/coding/rss-comics
./scripts/local_comicskingdom_update.sh
```

### Check GitHub Actions

Visit: https://github.com/adamprime/comiccaster/actions

### Check Netlify Deployment

Visit: https://app.netlify.com/sites/comiccaster/deploys

## Troubleshooting

### Local Script Not Running

```bash
# Check if agent is loaded
launchctl list | grep comicskingdom

# Reload agent
launchctl unload ~/Library/LaunchAgents/com.comiccaster.comicskingdom.plist
launchctl load ~/Library/LaunchAgents/com.comiccaster.comicskingdom.plist

# Check logs for errors
tail -100 ~/coding/rss-comics/logs/comicskingdom_local.log
```

### Comics Kingdom Cookies Expired

If cookies expire (every ~60 days):

```bash
cd ~/coding/rss-comics
source venv/bin/activate
python scripts/reauth_comicskingdom.py
```

This will:
1. Open a browser window
2. Wait for you to solve reCAPTCHA and login
3. Save fresh cookies
4. Next run will use new cookies

### GitHub Actions Not Finding Comics Kingdom Data

Check that data files are committed:

```bash
git ls-files data/comicskingdom_*.json
```

If missing:

```bash
git add data/comicskingdom_*.json
git commit -m "Add Comics Kingdom data"
git push
```

## Uninstalling

To remove the local automation:

```bash
# Unload the agent
launchctl unload ~/Library/LaunchAgents/com.comiccaster.comicskingdom.plist

# Remove the plist file
rm ~/Library/LaunchAgents/com.comiccaster.comicskingdom.plist

# Optionally remove log files
rm -rf ~/coding/rss-comics/logs/
```

## Files

- `scripts/local_comicskingdom_update.sh` - Main local scraping script
- `scripts/install_local_automation.sh` - Installer for launchd agent
- `scripts/com.comiccaster.comicskingdom.plist` - launchd configuration
- `scripts/generate_comicskingdom_feeds.py` - Feed generator (runs in GitHub Actions)
- `.github/workflows/update-feeds.yml` - GitHub Actions workflow
- `data/comicskingdom_*.json` - Scraped data files (git tracked)
- `data/comicskingdom_cookies.pkl` - Authentication cookies (git ignored)

## Notes

- **Mac Must Be On**: Your Mac needs to be running (not shut down) at 12:30 AM for the script to run
  - Sleep is OK - launchd will wake it
  - Shutdown/power off will prevent the script from running
- **Network Required**: Needs internet connection to scrape and push to GitHub
- **Timing**: Local script runs 30 minutes before GitHub Actions to ensure data is available
- **Fallback**: If local script doesn't run, GitHub Actions will still update GoComics feeds
