#!/bin/bash
# Master ComicCaster Update Script
# Runs all scraping and feed generation locally
# Schedule: 3:00 AM CST daily via LaunchD

set -e
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$REPO_DIR"

LOG_FILE="$REPO_DIR/logs/master_update.log"
mkdir -p "$REPO_DIR/logs"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "================================================================================"
echo "ComicCaster Master Update - $(date)"
echo "================================================================================"

# Load environment variables (.env has GoComics credentials)
if [ -f "$REPO_DIR/.env" ]; then
    export $(grep -v '^#' "$REPO_DIR/.env" | xargs)
fi

# Activate virtual environment
source "$REPO_DIR/venv/bin/activate"

# Install comiccaster package in editable mode (if not already installed)
pip install -e "$REPO_DIR" > /dev/null 2>&1 || true

# Clean git refs
echo ""
echo "Cleaning up git references..."
git fetch --all --prune 2>/dev/null || true
git gc --prune=now 2>/dev/null || true
git pull origin main || true

# Phase 1: Scrape all sources (sequential for reliability)
echo ""
echo "=== Phase 1: Scraping All Sources ==="
DATE_STR=$(date +%Y-%m-%d)

echo ""
echo "[1/4] Scraping GoComics (authenticated)..."
python scripts/authenticated_scraper_secure.py --output-dir ./data
if [ $? -ne 0 ]; then
    echo "❌ GoComics scraping failed"
    osascript -e 'display notification "GoComics scraping failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

echo ""
echo "[2/4] Scraping Comics Kingdom..."
python scripts/comicskingdom_scraper_individual.py --date "$DATE_STR" --output-dir data
if [ $? -ne 0 ]; then
    echo "❌ Comics Kingdom scraping failed"
    osascript -e 'display notification "Comics Kingdom scraping failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

echo ""
echo "[3/4] Scraping TinyView..."
python scripts/tinyview_scraper_local_authenticated.py --date "$DATE_STR" --days-back 15
if [ $? -ne 0 ]; then
    echo "❌ TinyView scraping failed"
    osascript -e 'display notification "TinyView scraping failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

echo ""
echo "[4/4] Scraping Far Side..."
python scripts/update_farside_feeds.py
if [ $? -ne 0 ]; then
    echo "❌ Far Side scraping failed"
    osascript -e 'display notification "Far Side scraping failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

# Phase 2: Generate all feeds from scraped data
echo ""
echo "=== Phase 2: Generating All Feeds ==="

echo ""
echo "[1/3] Generating GoComics feeds..."
python scripts/update_feeds.py
if [ $? -ne 0 ]; then
    echo "❌ GoComics feed generation failed"
    osascript -e 'display notification "GoComics feed generation failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

echo ""
echo "[2/3] Generating Comics Kingdom feeds..."
python scripts/generate_comicskingdom_feeds.py
if [ $? -ne 0 ]; then
    echo "❌ Comics Kingdom feed generation failed"
    osascript -e 'display notification "Comics Kingdom feed generation failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

echo ""
echo "[3/3] Generating TinyView feeds..."
python scripts/generate_tinyview_feeds_from_data.py
if [ $? -ne 0 ]; then
    echo "❌ TinyView feed generation failed"
    osascript -e 'display notification "TinyView feed generation failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    exit 1
fi

# Phase 3: Commit and push everything once
echo ""
echo "=== Phase 3: Committing and Pushing ==="

git add -f data/*.json public/feeds/*.xml

if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    git commit -m "Update all comic feeds for $DATE_STR

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
    
    # Push with simple retry (rare with single push)
    for i in {1..3}; do
        if git push origin main; then
            echo "✅ Successfully pushed all updates"
            
            # Send success notification
            osascript -e 'display notification "All feeds updated successfully" with title "ComicCaster: Success" sound name "Glass"' 2>/dev/null || true
            
            # Optional email notification (if mail command is available)
            if command -v mail &> /dev/null; then
                echo "ComicCaster: All feeds updated successfully for $DATE_STR" | \
                    mail -s "ComicCaster: Success" adam@tervort.org
            fi
            
            break
        else
            echo "⚠️  Push failed (attempt $i/3)"
            if [ $i -lt 3 ]; then
                git pull --rebase origin main
                sleep 2
            else
                echo "❌ Failed to push after 3 attempts"
                
                # Send failure notification
                osascript -e 'display notification "Failed to push updates" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
                
                # Optional email notification
                if command -v mail &> /dev/null; then
                    echo "ComicCaster: Update failed - check logs at $LOG_FILE" | \
                        mail -s "ComicCaster: FAILURE" adam@tervort.org
                fi
                
                exit 1
            fi
        fi
    done
fi

echo ""
echo "================================================================================"
echo "ComicCaster Master Update Complete - $(date)"
echo "================================================================================"
