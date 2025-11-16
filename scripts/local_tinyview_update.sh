#!/bin/bash

# Local TinyView Update Script
# This script runs on your local Mac to scrape TinyView comics and push to GitHub
# Similar to Comics Kingdom, but for TinyView
#
# Schedule: Runs at 12:35 AM daily (5 minutes after Comics Kingdom)
#
# What it does:
# 1. Scrapes all TinyView comics (last 15 days)
# 2. Saves data to data/tinyview_YYYY-MM-DD.json
# 3. Commits and pushes to GitHub
# 4. GitHub Actions will read this data and generate feeds

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Log file
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/tinyview_local.log"

# Function to log with timestamp
log() {
    echo -e "${GREEN}$(date '+%Y-%m-%d %H:%M:%S')${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}$(date '+%Y-%m-%d %H:%M:%S') ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}$(date '+%Y-%m-%d %H:%M:%S') WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Start logging
echo "" >> "$LOG_FILE"
log "================================================================================"
log "TinyView Local Update Started"
log "================================================================================"

# Change to project directory
cd "$PROJECT_DIR"
log "Working directory: $PROJECT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    log "Activating virtual environment..."
    source venv/bin/activate
else
    log_error "Virtual environment not found at venv/"
    exit 1
fi

# Get today's date
DATE=$(date '+%Y-%m-%d')
log "Scraping date: $DATE"

# Check if data file already exists
DATA_FILE="data/tinyview_$DATE.json"
if [ -f "$DATA_FILE" ]; then
    log_warning "Data file already exists: $DATA_FILE"
    log "Overwriting with fresh data..."
fi

# Run the TinyView scraper
log "Starting TinyView scraper..."
log "This may take 5-10 minutes for 30 comics..."

if python3 tinyview_scraper_local.py --date "$DATE" --days-back 15 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ TinyView scraping completed successfully"
else
    log_error "❌ TinyView scraping failed"
    exit 1
fi

# Check if data file was created
if [ ! -f "$DATA_FILE" ]; then
    log_error "Data file was not created: $DATA_FILE"
    exit 1
fi

log "✅ Data file created: $DATA_FILE"

# Commit and push to GitHub
log "Committing and pushing TinyView data..."

git add "$DATA_FILE"

if git diff --staged --quiet; then
    log_warning "No changes to commit (data file unchanged)"
else
    git commit -m "Update TinyView data for $DATE" \
        -m "Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
    
    if git push; then
        log "✅ Successfully pushed TinyView data to GitHub"
        log "   GitHub Actions will now generate feeds automatically"
    else
        log_error "Failed to push to GitHub"
        log_error "Run 'git push' manually to sync"
        exit 1
    fi
fi

log "================================================================================"
log "TinyView Local Update Complete - $(date)"
log "================================================================================"

exit 0
