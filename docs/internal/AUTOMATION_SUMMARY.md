# ComicCaster Automation Summary

## Daily Update Schedule

### 2:30 AM CST - Comics Kingdom (Local Mac)
- **Script**: `scripts/local_comicskingdom_update.sh`
- **What it does**:
  - Scrapes all 119 Comics Kingdom comics
  - Saves to `data/comicskingdom_YYYY-MM-DD.json`
  - Commits and pushes to GitHub via SSH
- **Automation**: launchd agent `com.comiccaster.comicskingdom`
- **Logs**: `logs/comicskingdom_local.log`

### 2:35 AM CST - TinyView (Local Mac)
- **Script**: `scripts/local_tinyview_update.sh`
- **What it does**:
  - Scrapes all 12 active TinyView comics (15 days back)
  - Saves to `data/tinyview_YYYY-MM-DD.json`
  - Commits and pushes to GitHub via SSH
- **Automation**: launchd agent `com.comiccaster.tinyview`
- **Logs**: `logs/tinyview_local.log`

### 3:00 AM CST - Feed Generation (GitHub Actions)
- **Workflow**: `.github/workflows/update-feeds.yml`
- **Scheduled**: 9:00 AM UTC = 3:00 AM CST
- **What it does**:
  1. Scrapes GoComics (400+ comics)
  2. Reads Comics Kingdom data from `data/comicskingdom_*.json`
  3. Reads TinyView data from `data/tinyview_*.json`
  4. Generates all RSS feeds (600+ feeds)
  5. Commits and pushes updated feeds
- **Trigger**: Also runs on manual workflow dispatch
- **Logs**: GitHub Actions workflow runs

### Continuous - Netlify Deploy
- **What it does**: Automatically deploys when feeds are pushed
- **Result**: Updated feeds live at https://comiccaster.xyz

## Why This Schedule Works

1. **Local scraping at 2:30 AM** ensures Comics Kingdom and TinyView data is fresh
2. **GitHub Actions at 3:00 AM** has recent data to work with
3. **No conflicts** - local scraping completes before GitHub Actions starts
4. **SSH authentication** allows background jobs to push without keychain access

## Monitoring

### Check if scripts ran successfully:

```bash
# View recent logs
tail -50 ~/coding/rss-comics/logs/comicskingdom_local.log
tail -50 ~/coding/rss-comics/logs/tinyview_local.log

# Check today's data files
ls -lh ~/coding/rss-comics/data/*$(date +%Y-%m-%d)*

# Check recent commits
cd ~/coding/rss-comics && git log --oneline -5 | grep "Update"

# Check launchd status
launchctl list | grep comiccaster
```

### Expected output each morning:

```bash
$ ls -lh ~/coding/rss-comics/data/*2025-11-17*
-rw-r--r--  comicskingdom_2025-11-17.json  (119 comics)
-rw-r--r--  tinyview_2025-11-17.json       (60-70 comics)

$ git log --oneline -3
abc1234 Update comic feeds
def5678 Update TinyView data for 2025-11-17
ghi9012 Update Comics Kingdom data for 2025-11-17
```

## Manual Triggers

### Run scripts manually (testing):

```bash
# Comics Kingdom
cd ~/coding/rss-comics
bash scripts/local_comicskingdom_update.sh

# TinyView
bash scripts/local_tinyview_update.sh

# GitHub Actions
cd ~/coding/rss-comics
gh workflow run "Update Comic Feeds"
```

### View running/recent workflows:

```bash
gh run list --workflow="Update Comic Feeds" --limit 5
gh run watch  # Watch the currently running workflow
```

## Troubleshooting

### Scripts ran but didn't push?

**Problem**: `failed to get: -25320` or `Device not configured`

**Solution**: Already fixed! Using SSH instead of HTTPS.

**Verify**: 
```bash
cd ~/coding/rss-comics && git remote -v
# Should show: git@github.com:adamprime/comiccaster.git
```

### GitHub Actions timed out?

**Problem**: GoComics scraping takes too long

**Solution**: Workflow has 90s timeout per request with retries. If it continues to fail, GoComics may be rate-limiting.

**Check**: View workflow logs at https://github.com/adamprime/comiccaster/actions

### Want to disable automation?

```bash
# Unload launchd agents
launchctl unload ~/Library/LaunchAgents/com.comiccaster.comicskingdom.plist
launchctl unload ~/Library/LaunchAgents/com.comiccaster.tinyview.plist

# Re-enable later
launchctl load ~/Library/LaunchAgents/com.comiccaster.comicskingdom.plist
launchctl load ~/Library/LaunchAgents/com.comiccaster.tinyview.plist
```

## Re-authentication Schedule

### Comics Kingdom Cookies (~60 days)

When cookies expire (every 60 days), run:

```bash
cd ~/coding/rss-comics
python scripts/reauth_comicskingdom.py
```

This will:
1. Open browser
2. Let you solve reCAPTCHA
3. Save fresh cookies
4. Continue working for another 60 days

**Track cookie age**:
```bash
ls -lh ~/coding/rss-comics/data/comicskingdom_cookies.pkl
```

### GoComics Credentials

Stored in GitHub Secrets, no maintenance needed.

### TinyView

No authentication required - public comics only.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  LOCAL MAC (2:30 AM - 2:40 AM CST)                          │
├─────────────────────────────────────────────────────────────┤
│  launchd triggers:                                          │
│  • Comics Kingdom scraper → data/comicskingdom_*.json       │
│  • TinyView scraper → data/tinyview_*.json                  │
│  • git commit + push via SSH                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ git push
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  GITHUB REPOSITORY                                          │
│  • data/comicskingdom_*.json                                │
│  • data/tinyview_*.json                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ scheduled (3:00 AM CST)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  GITHUB ACTIONS (3:00 AM - 3:05 AM CST)                     │
├─────────────────────────────────────────────────────────────┤
│  1. Scrape GoComics (400+ comics)                           │
│  2. Read Comics Kingdom data from repo                      │
│  3. Read TinyView data from repo                            │
│  4. Generate 600+ RSS feeds                                 │
│  5. git commit + push feeds                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ git push
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  GITHUB REPOSITORY                                          │
│  • public/feeds/*.xml (600+ feeds)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ webhook
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  NETLIFY (automatic deploy)                                 │
│  https://comiccaster.xyz                                    │
└─────────────────────────────────────────────────────────────┘
```

## Success Criteria

Each morning, verify:
- ✅ Two new data files in `data/`
- ✅ Three new commits in git log
- ✅ Feeds updated on comiccaster.xyz
- ✅ No error notifications

All working? You're good to go! 🎉
