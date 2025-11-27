# Comics Kingdom - Favoriting All Comics

To get ALL Comics Kingdom comics in your daily scrapes, you need to favorite them on the Comics Kingdom website (one-time setup).

## Why?

Comics Kingdom's favorites page shows all comics that have updates for the current day - but only for comics you've favorited. By favoriting all comics, the automated scraper can get everything in one efficient page load.

## Setup Steps

### 1. Login to Comics Kingdom

Visit: https://comicskingdom.com/login

### 2. Visit the All Comics Page

Visit: https://comicskingdom.com/features

This shows all 136+ comics in alphabetical order.

### 3. Favorite All Comics

For each comic:
1. Click on the comic
2. Click the "Add to Favorites" button (heart icon)
3. Go back and repeat for the next comic

**Time estimate**: ~15-20 minutes for all 136 comics

### 4. Verify

Visit your favorites page: https://comicskingdom.com/favorites

You should see all comics that have updates for today. On an average day, expect 80-120 comics to have updates (not all comics update daily).

## Alternative: Bulk Favoriting (If Available)

Check if Comics Kingdom has a "Favorite All" feature:
1. Visit the Features page
2. Look for a "Select All" or "Favorite All" option
3. If available, use it to favorite everything at once

## After Setup

Once all comics are favorited:
- The local scraper will automatically get all daily updates
- Scraping happens at 12:30 AM via the automated script
- No authentication issues (cookies last ~60 days)
- Efficient - one page load gets all updates

## Maintenance

- No daily maintenance required
- Every ~60 days: Re-authenticate when cookies expire (run `python scripts/reauth_comicskingdom.py`)
- Occasionally: Check if new comics were added to Comics Kingdom and favorite them

## Current Status

As of 2025-11-15:
- **136 Comics Kingdom comics** added to catalog
- **18 comics** scraped today (likely only 18 had updates or only 18 are favorited)
- **To get all daily updates**: Favorite all 136 comics on the website

## Testing

After favoriting all comics, test the scraper:

```bash
cd ~/coding/rss-comics
./scripts/local_comicskingdom_update.sh
```

Check the output - you should see many more than 18 comics scraped.
