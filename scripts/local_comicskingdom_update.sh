#!/bin/bash
# Local Comics Kingdom scraper - runs on your Mac via cron
# Scrapes Comics Kingdom, commits data, and pushes to GitHub
# GitHub Actions will then generate feeds from this data

set -e  # Exit on any error

# Change to repository directory
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$REPO_DIR"

# Log file for debugging
LOG_FILE="$REPO_DIR/logs/comicskingdom_local.log"
mkdir -p "$REPO_DIR/logs"

# Redirect all output to log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "================================================================================"
echo "Comics Kingdom Local Update - $(date)"
echo "================================================================================"

# Load environment variables from .env if it exists
if [ -f "$REPO_DIR/.env" ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' "$REPO_DIR/.env" | xargs)
fi

# Check required environment variables
if [ -z "$COMICSKINGDOM_USERNAME" ] || [ -z "$COMICSKINGDOM_PASSWORD" ]; then
    echo "❌ Error: COMICSKINGDOM_USERNAME and COMICSKINGDOM_PASSWORD must be set"
    echo "   Either set them in .env file or as environment variables"
    exit 1
fi

# Activate virtual environment
if [ -d "$REPO_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$REPO_DIR/venv/bin/activate"
else
    echo "❌ Error: Virtual environment not found at $REPO_DIR/venv"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Clean up git refs to prevent lock errors
echo ""
echo "Cleaning up git references..."
git fetch --all --prune 2>/dev/null || echo "⚠️  Warning: Could not fetch (working offline?)"
git gc --prune=now 2>/dev/null || echo "⚠️  Warning: Could not run gc"

# Pull latest changes first (in case of conflicts)
echo ""
echo "Pulling latest changes from GitHub..."
git pull origin main || {
    echo "⚠️  Warning: Could not pull latest changes (working offline or conflicts?)"
}

# Run Comics Kingdom scraper (gets all favorited comics from favorites page)
echo ""
echo "Running Comics Kingdom scraper (individual pages)..."
DATE_STR=$(date +%Y-%m-%d)
python comicskingdom_scraper_individual.py --date "$DATE_STR" --output-dir data

if [ $? -eq 0 ]; then
    echo "✅ Comics Kingdom scraping completed successfully"
else
    echo "❌ Comics Kingdom scraping failed"
    exit 1
fi

# Check if data file was created
DATA_FILE="data/comicskingdom_${DATE_STR}.json"
if [ ! -f "$DATA_FILE" ]; then
    echo "❌ Error: Expected data file not found: $DATA_FILE"
    exit 1
fi

echo "✅ Data file created: $DATA_FILE"

# Git commit and push
echo ""
echo "Committing and pushing Comics Kingdom data..."
git add data/comicskingdom_*.json
# Note: Cookies are NOT added to git (they're in .gitignore for security)

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "ℹ️  No changes to commit (data already up to date)"
else
    git commit -m "Update Comics Kingdom data for $DATE_STR

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
    
    # Push with retry logic in case of race conditions with GitHub Actions
    echo "Pushing to GitHub..."
    MAX_RETRIES=3
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if git push origin main; then
            echo "✅ Successfully pushed Comics Kingdom data to GitHub"
            echo "   GitHub Actions will now generate feeds automatically"
            break
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "⚠️  Push failed (attempt $RETRY_COUNT/$MAX_RETRIES)"
                echo "   Pulling latest changes and retrying..."
                
                # Pull with rebase to incorporate remote changes
                git pull --rebase origin main
                
                if [ $? -ne 0 ]; then
                    echo "❌ Failed to pull and rebase changes"
                    exit 1
                fi
                
                sleep 2
            else
                echo "❌ Failed to push after $MAX_RETRIES attempts"
                exit 1
            fi
        fi
    done
fi

echo ""
echo "================================================================================"
echo "Comics Kingdom Local Update Complete - $(date)"
echo "================================================================================"
echo ""
