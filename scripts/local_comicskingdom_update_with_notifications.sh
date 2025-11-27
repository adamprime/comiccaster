#!/bin/bash

# Comics Kingdom Local Update Script with Notifications
# This script scrapes Comics Kingdom comics and sends notifications on completion

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Setup Python path and environment
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Check for uncommitted changes and stash if needed
STASH_NEEDED=false
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Stashing uncommitted changes..."
    git stash push -u -m "Auto-stash before Comics Kingdom update"
    STASH_NEEDED=true
fi

# Pull latest changes FIRST (before scraping)
echo ""
echo "Pulling latest changes from GitHub..."
if git pull --rebase origin main; then
    echo "✅ Synced with remote"
else
    echo "⚠️  Rebase had conflicts, trying merge..."
    git rebase --abort 2>/dev/null
    if git pull origin main; then
        echo "✅ Synced with remote (merge)"
    else
        echo "❌ Failed to pull from GitHub"
        exit 1
    fi
fi

# Restore stashed changes if we stashed any
if [ "$STASH_NEEDED" = true ]; then
    echo "Restoring stashed changes..."
    # Don't exit on error for stash pop - it may succeed with warnings
    set +e
    git stash pop > /tmp/stash_pop.log 2>&1
    STASH_EXIT=$?
    set -e
    
    if [ $STASH_EXIT -eq 0 ]; then
        echo "✅ Restored changes"
    else
        echo "⚠️  Stash pop returned exit code $STASH_EXIT"
        echo "   Changes may have been restored with conflicts"
        echo "   Check 'git status' and 'git stash list' if needed"
        # Continue anyway - the stash may have been applied despite the warning
    fi
fi

# Activate venv if it exists
if [ -d "venv/bin" ]; then
    source venv/bin/activate
fi

# Date for scraping
DATE_STR=$(date +%Y-%m-%d)
DATA_FILE="data/comicskingdom_$DATE_STR.json"

echo ""
echo "================================================================================"
echo "Comics Kingdom Scraper - $(date)"
echo "================================================================================"
echo ""
echo "Scraping Comics Kingdom for $DATE_STR..."
echo ""

# Run the scraper
if python comicskingdom_scraper_individual.py --date "$DATE_STR" --output-dir data 2>&1 | tee -a logs/comicskingdom_local.log; then
    echo ""
    echo "✅ Comics Kingdom scraping completed successfully"
    
    # Count comics scraped
    if [ -f "$DATA_FILE" ]; then
        COMIC_COUNT=$(python3 -c "import json; print(len(json.load(open('$DATA_FILE'))))" 2>/dev/null || echo "unknown")
        echo "   Scraped $COMIC_COUNT comics"
    else
        COMIC_COUNT="unknown"
    fi
else
    echo ""
    echo "❌ Comics Kingdom scraping failed"
    
    # Send failure notification
    osascript -e 'display notification "Comics Kingdom scraping failed - check logs" with title "ComicCaster Error" sound name "Basso"' 2>/dev/null || true
    
    # Optional: Send email notification for failures
    # if command -v mail &> /dev/null; then
    #     echo "Comics Kingdom scraping failed. Check logs at $PROJECT_DIR/logs/comicskingdom_local.log" | \
    #         mail -s "ComicCaster: Comics Kingdom FAILED" your-email@example.com
    # fi
    
    exit 1
fi

echo ""
echo "Checking data file..."
if [ ! -f "$DATA_FILE" ]; then
    echo "❌ Data file not created: $DATA_FILE"
    exit 1
fi

echo "✅ Data file created: $DATA_FILE"

# Git commit and push
echo ""
echo "Committing and pushing Comics Kingdom data..."
git add data/comicskingdom_*.json

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "ℹ️  No changes to commit (data already up to date)"
else
    git commit -m "Update Comics Kingdom data for $DATE_STR

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
    
    # Push directly (we already pulled at the start)
    if git push origin main; then
        echo "✅ Successfully pushed Comics Kingdom data to GitHub"
        echo "   GitHub Actions will now generate feeds automatically"
    else
        echo "❌ Failed to push to GitHub"
        echo "   This might mean someone else pushed while we were scraping"
        echo "   Run 'git pull --rebase && git push' manually to sync"
        exit 1
    fi
fi

echo ""
echo "================================================================================"
echo "Comics Kingdom Local Update Complete - $(date)"
echo "================================================================================"

# Send success notification
osascript -e "display notification \"Successfully scraped $COMIC_COUNT comics\" with title \"ComicCaster: Comics Kingdom\" subtitle \"Update Complete\" sound name \"Glass\"" 2>/dev/null || true

# Optional: Send email notification (uncomment and configure to enable)
# if command -v mail &> /dev/null; then
#     echo "Comics Kingdom update completed successfully. Scraped $COMIC_COUNT comics." | \
#         mail -s "ComicCaster: Comics Kingdom Complete" your-email@example.com
# fi

echo ""
exit 0
