#!/bin/bash

# Local TinyView Update Script (Authenticated)
# This script runs on your local Mac to scrape TinyView comics and push to GitHub
# Uses persistent Chrome profile for authentication - no manual intervention needed!
#
# Schedule: Runs at 12:35 AM daily (5 minutes after Comics Kingdom)
#
# What it does:
# 1. Scrapes all TinyView comics using authenticated session (last 15 days)
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
log "TinyView Local Update Started (Authenticated)"
log "================================================================================"

# Change to project directory
cd "$PROJECT_DIR"
log "Working directory: $PROJECT_DIR"

# Check for uncommitted changes and stash if needed
STASH_NEEDED=false
if ! git diff --quiet || ! git diff --cached --quiet; then
    log "Stashing uncommitted changes..."
    git stash push -u -m "Auto-stash before TinyView update"
    STASH_NEEDED=true
fi

# Clean up git refs to prevent lock errors
log "Cleaning up git references..."
git fetch --all --prune 2>/dev/null || log_warning "Could not fetch (working offline?)"
git gc --prune=now 2>/dev/null || log_warning "Could not run gc"

# Pull latest changes FIRST (before scraping)
log "Pulling latest changes from GitHub..."
if git pull --rebase origin main; then
    log "✅ Synced with remote"
else
    log_warning "Rebase had conflicts, trying merge..."
    git rebase --abort 2>/dev/null
    if git pull origin main; then
        log "✅ Synced with remote (merge)"
    else
        log_error "Failed to pull from GitHub"
        exit 1
    fi
fi

# Restore stashed changes if we stashed any
if [ "$STASH_NEEDED" = true ]; then
    log "Restoring stashed changes..."
    # Don't exit on error for stash pop - it may succeed with warnings
    set +e
    git stash pop > /tmp/stash_pop.log 2>&1
    STASH_EXIT=$?
    set -e
    
    if [ $STASH_EXIT -eq 0 ]; then
        log "✅ Restored changes"
    else
        log_warning "Stash pop returned exit code $STASH_EXIT"
        log_warning "Changes may have been restored with conflicts"
        log_warning "Check 'git status' and 'git stash list' if needed"
        # Continue anyway - the stash may have been applied despite the warning
    fi
fi

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

# Run the authenticated TinyView scraper
log "Starting authenticated TinyView scraper..."
log "Using persistent Chrome profile for authentication"
log "This may take 5-10 minutes for 29 comics..."

if python3 scripts/tinyview_scraper_local_authenticated.py --date "$DATE" --days-back 15 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ TinyView scraping completed successfully"
else
    log_error "❌ TinyView scraping failed"
    
    # Send failure notification
    osascript -e 'display notification "TinyView scraping failed - check logs" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    
    exit 1
fi

# Check if data file was created
if [ ! -f "$DATA_FILE" ]; then
    log_error "Data file was not created: $DATA_FILE"
    exit 1
fi

log "✅ Data file created: $DATA_FILE"

# Count comics scraped
COMIC_COUNT=$(cat "$DATA_FILE" | python3 -c "import json, sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "unknown")
log "   Scraped $COMIC_COUNT comic strips"

# Commit and push to GitHub
log "Committing and pushing TinyView data..."

git add "$DATA_FILE"

if git diff --staged --quiet; then
    log_warning "No changes to commit (data file unchanged)"
else
    git commit -m "Update TinyView data for $DATE" \
        -m "Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
    
    # Push with retry logic in case of race conditions with GitHub Actions
    log "Pushing to GitHub..."
    MAX_RETRIES=3
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if git push; then
            log "✅ Successfully pushed TinyView data to GitHub"
            log "   GitHub Actions will now generate feeds automatically"
            break
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                log_warning "Push failed (attempt $RETRY_COUNT/$MAX_RETRIES)"
                log "Pulling latest changes and retrying..."
                
                # Pull with rebase to incorporate remote changes
                if git pull --rebase origin main; then
                    log "✅ Rebased successfully"
                    sleep 2
                else
                    log_error "Failed to pull and rebase changes"
                    exit 1
                fi
            else
                log_error "Failed to push after $MAX_RETRIES attempts"
                exit 1
            fi
        fi
    done
fi

log "================================================================================"
log "TinyView Local Update Complete - $(date)"
log "================================================================================"

# Send macOS notification
osascript -e "display notification \"Successfully scraped $COMIC_COUNT strips\" with title \"ComicCaster: TinyView\" subtitle \"Update Complete\" sound name \"Glass\"" 2>/dev/null || true

# Optional: Send email notification (uncomment and configure to enable)
# if command -v mail &> /dev/null; then
#     echo "TinyView update completed successfully. Scraped $COMIC_COUNT comics." | \
#         mail -s "ComicCaster: TinyView Update Complete" your-email@example.com
# fi

exit 0
