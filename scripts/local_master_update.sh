#!/bin/bash
# Master ComicCaster Update Script
# Runs all scraping and feed generation locally
# Schedule: 3:05 AM CST daily via LaunchD
#
# Design: Individual scraper/feed failures do NOT kill the pipeline.
# Whatever succeeds gets committed and pushed. Failures are logged
# and a notification is sent summarizing what broke.

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$REPO_DIR"

LOG_FILE="$REPO_DIR/logs/master_update.log"
mkdir -p "$REPO_DIR/logs"

# Rotate log if it exceeds 10MB
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0) -gt 10485760 ]; then
    mv "$LOG_FILE" "$LOG_FILE.prev"
fi

exec > >(tee -a "$LOG_FILE") 2>&1

echo "================================================================================"
echo "ComicCaster Master Update - $(date)"
echo "================================================================================"

# Track failures
FAILURES=()

# Load environment variables (.env has GoComics credentials)
if [ -f "$REPO_DIR/.env" ]; then
    export $(grep -v '^#' "$REPO_DIR/.env" | xargs)
fi

# Activate virtual environment
source "$REPO_DIR/venv/bin/activate"

# Install comiccaster package in editable mode (if not already installed)
pip install -e "$REPO_DIR" > /dev/null 2>&1 || true

# Load SSH key from Keychain (required for LaunchD which runs without GUI session)
ssh-add --apple-use-keychain ~/.ssh/id_rsa 2>/dev/null || true

# Verify GitHub SSH access before proceeding
if ! ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "❌ GitHub SSH authentication failed - check SSH key and keychain"
    osascript -e 'display notification "SSH auth failed - check keychain" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    # This is fatal -- we can't push anything without SSH
    echo "Aborting: Cannot push without SSH access."
    echo "================================================================================"
    echo "ComicCaster Master Update ABORTED (SSH) - $(date)"
    echo "================================================================================"
    exit 0  # Exit 0 so LaunchD doesn't retry endlessly
fi
echo "✅ GitHub SSH authentication verified"

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
echo "[1/5] Scraping GoComics (authenticated)..."
if python scripts/authenticated_scraper_secure.py --output-dir ./data; then
    echo "✅ GoComics scraping succeeded"
else
    echo "❌ GoComics scraping failed"
    FAILURES+=("GoComics scraping")
fi

echo ""
echo "[2/5] Scraping Comics Kingdom..."
if python scripts/comicskingdom_scraper_individual.py --date "$DATE_STR" --output-dir data; then
    echo "✅ Comics Kingdom scraping succeeded"
else
    echo "❌ Comics Kingdom scraping failed"
    FAILURES+=("Comics Kingdom scraping")
fi

echo ""
echo "[3/5] Scraping TinyView..."
if python scripts/tinyview_scraper_local_authenticated.py --date "$DATE_STR" --days-back 15; then
    echo "✅ TinyView scraping succeeded"
else
    echo "❌ TinyView scraping failed"
    FAILURES+=("TinyView scraping")
fi

echo ""
echo "[4/5] Scraping Far Side..."
if python scripts/update_farside_feeds.py; then
    echo "✅ Far Side scraping succeeded"
else
    echo "❌ Far Side scraping failed"
    FAILURES+=("Far Side scraping")
fi

echo ""
echo "[5/5] Scraping New Yorker Daily Cartoon..."
if python scripts/update_newyorker_feeds.py; then
    echo "✅ New Yorker scraping succeeded"
else
    echo "❌ New Yorker scraping failed"
    FAILURES+=("New Yorker scraping")
fi

# Phase 2: Generate all feeds from scraped data
# Run all generators regardless of scraper results -- they use whatever data exists
echo ""
echo "=== Phase 2: Generating All Feeds ==="

echo ""
echo "[1/4] Generating GoComics feeds..."
if python scripts/update_feeds.py; then
    echo "✅ GoComics feed generation succeeded"
else
    echo "❌ GoComics feed generation failed"
    FAILURES+=("GoComics feed generation")
fi

echo ""
echo "[2/4] Generating Comics Kingdom feeds..."
if python scripts/generate_comicskingdom_feeds.py; then
    echo "✅ Comics Kingdom feed generation succeeded"
else
    echo "❌ Comics Kingdom feed generation failed"
    FAILURES+=("Comics Kingdom feed generation")
fi

echo ""
echo "[3/4] Generating TinyView feeds..."
if python scripts/generate_tinyview_feeds_from_data.py; then
    echo "✅ TinyView feed generation succeeded"
else
    echo "❌ TinyView feed generation failed"
    FAILURES+=("TinyView feed generation")
fi

echo ""
echo "[4/4] Generating Creators feeds..."
if python scripts/generate_creators_feeds.py; then
    echo "✅ Creators feed generation succeeded"
else
    echo "❌ Creators feed generation failed"
    FAILURES+=("Creators feed generation")
fi

# Phase 3: Commit and push everything that succeeded
echo ""
echo "=== Phase 3: Committing and Pushing ==="

git add -f data/*.json public/feeds/*.xml

if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    git commit -m "Update all comic feeds for $DATE_STR

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"

    # Push with simple retry
    PUSH_OK=false
    for i in {1..3}; do
        if git push origin main; then
            echo "✅ Successfully pushed all updates"
            PUSH_OK=true
            break
        else
            echo "⚠️  Push failed (attempt $i/3)"
            if [ $i -lt 3 ]; then
                git pull --rebase origin main
                sleep 2
            fi
        fi
    done

    if [ "$PUSH_OK" = false ]; then
        echo "❌ Failed to push after 3 attempts"
        FAILURES+=("Git push")
    fi
fi

# Summary and notifications
echo ""
echo "================================================================================"
if [ ${#FAILURES[@]} -eq 0 ]; then
    echo "ComicCaster Master Update Complete (ALL SUCCESS) - $(date)"
    osascript -e 'display notification "All feeds updated successfully" with title "ComicCaster: Success" sound name "Glass"' 2>/dev/null || true
else
    FAIL_LIST=$(IFS=', '; echo "${FAILURES[*]}")
    echo "ComicCaster Master Update Complete with FAILURES - $(date)"
    echo "Failed steps: $FAIL_LIST"
    osascript -e "display notification \"Failed: $FAIL_LIST\" with title \"ComicCaster: Partial Failure\" sound name \"Basso\"" 2>/dev/null || true
fi
echo "================================================================================"

# Always exit 0 -- LaunchD should not retry on failure.
# The daily schedule will run it again tomorrow.
# If something needs immediate attention, the notification tells you.
exit 0
