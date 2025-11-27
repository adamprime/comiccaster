# ComicCaster Notification Setup

## Quick Setup: Add macOS Notifications

Add these lines to your existing scripts to get notifications when scraping completes.

### For Comics Kingdom Script

Edit `scripts/local_comicskingdom_update.sh`:

**1. Add notification on SUCCESS** (before the final `exit 0`):

```bash
# Send success notification
COMIC_COUNT=$(python3 -c "import json; print(len(json.load(open('$DATA_FILE'))))" 2>/dev/null || echo "unknown")
osascript -e "display notification \"Successfully scraped $COMIC_COUNT comics\" with title \"ComicCaster: Comics Kingdom\" subtitle \"Update Complete\" sound name \"Glass\"" 2>/dev/null || true
```

**2. Add notification on FAILURE** (after "Comics Kingdom scraping failed"):

```bash
# Send failure notification
osascript -e 'display notification "Comics Kingdom scraping failed - check logs" with title \"ComicCaster: Error\" sound name \"Basso\"' 2>/dev/null || true
```

### For TinyView Script

Edit `scripts/local_tinyview_update.sh`:

**1. Add notification on SUCCESS** (before the final `exit 0`):

```bash
# Send success notification
COMIC_COUNT=$(python3 -c "import json; print(len(json.load(open('$DATA_FILE'))))" 2>/dev/null || echo "unknown")
osascript -e "display notification \"Successfully scraped $COMIC_COUNT comics\" with title \"ComicCaster: TinyView\" subtitle \"Update Complete\" sound name \"Glass\"" 2>/dev/null || true
```

**2. Add notification on FAILURE** (after "TinyView scraping failed"):

```bash
# Send failure notification
osascript -e 'display notification "TinyView scraping failed - check logs" with title \"ComicCaster: Error\" sound name \"Basso\"' 2>/dev/null || true
```

## What You'll See

When you wake up and check your Mac:

### Success Notification
```
┌─────────────────────────────────┐
│ ComicCaster: Comics Kingdom     │
│ Update Complete                 │
│ Successfully scraped 119 comics │
└─────────────────────────────────┘
```

### Failure Notification  
```
┌─────────────────────────────────┐
│ ComicCaster: Error              │
│ Comics Kingdom scraping failed  │
│ check logs                      │
└─────────────────────────────────┘
```

## Viewing Notifications

- **Notification Center**: Click the time in menu bar → See all notifications
- **Lock Screen**: Notifications appear when Mac wakes from sleep
- **Persistence**: Notifications stay in Notification Center until dismissed

## Optional: Email Notifications

If you want email notifications too, add this (after the osascript line):

```bash
# Optional: Email notification
if command -v mail &> /dev/null; then
    echo "Comics Kingdom update: Scraped $COMIC_COUNT comics" | \
        mail -s "ComicCaster: Update Complete" your-email@example.com
fi
```

**Note**: macOS `mail` command requires configuration. Most people prefer just the macOS notifications.

## Testing

Test notifications right now:

```bash
# Test success notification
osascript -e 'display notification "Test notification" with title "ComicCaster Test" sound name "Glass"'

# Test error notification  
osascript -e 'display notification "Test error" with title "ComicCaster Test" sound name "Basso"'
```

## Viewing Logs Anytime

Don't want to wait for notifications? Check logs manually:

```bash
# Comics Kingdom
tail -f ~/coding/rss-comics/logs/comicskingdom_local.log

# TinyView
tail -f ~/coding/rss-comics/logs/tinyview_local.log

# Or view last run
tail -50 ~/coding/rss-comics/logs/comicskingdom_local.log
```

## Sound Options

Available notification sounds (change `"Glass"` to any of these):
- `"Glass"` - Default success sound (recommended)
- `"Basso"` - Error sound (recommended for failures)
- `"Hero"` - Triumphant sound
- `"Ping"` - Subtle sound
- `"Blow"` - Whoosh sound

## Troubleshooting

**Notifications not showing?**

1. Check System Settings → Notifications → Script Editor → Allow Notifications
2. Make sure "Do Not Disturb" is off
3. Test with the test commands above
4. Check logs to verify scripts are running: `ls -la ~/coding/rss-comics/logs/`

**Want to disable notifications?**

Just remove the `osascript` lines from the scripts.
