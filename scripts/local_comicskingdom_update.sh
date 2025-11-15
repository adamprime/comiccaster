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

# Pull latest changes first (in case of conflicts)
echo ""
echo "Pulling latest changes from GitHub..."
git pull origin main || {
    echo "⚠️  Warning: Could not pull latest changes (working offline or conflicts?)"
}

# Run Comics Kingdom scraper
echo ""
echo "Running Comics Kingdom scraper..."
DATE_STR=$(date +%Y-%m-%d)
python comicskingdom_scraper_secure.py --date "$DATE_STR" --output-dir data

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
git add data/comicskingdom_cookies.pkl 2>/dev/null || true  # Add cookies if updated

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "ℹ️  No changes to commit (data already up to date)"
else
    git commit -m "Update Comics Kingdom data for $DATE_STR

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
    
    git push origin main
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully pushed Comics Kingdom data to GitHub"
        echo "   GitHub Actions will now generate feeds automatically"
    else
        echo "❌ Failed to push to GitHub"
        exit 1
    fi
fi

echo ""
echo "================================================================================"
echo "Comics Kingdom Local Update Complete - $(date)"
echo "================================================================================"
echo ""
