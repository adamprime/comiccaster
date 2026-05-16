#!/bin/bash
# ComicCaster pass-2 update — runs ~11:00 PT to capture late-publishing
# GoComics editorial cartoonists missed by the 03:20 PT pass-1 scrape.
#
# Scope: GoComics only. The other five sources don't share the same
# favorites-page timing dynamic (see docs/solutions/logic-errors/
# gocomics-favorites-page-timing.md), so we don't re-scrape them.
#
# Design: Reads pass-1's data/comics_$DATE.json, scrapes the GoComics
# favorites pages again, and merges any newly-published slugs into the
# same-day file via authenticated_scraper_secure.py --merge. Regenerates
# only GoComics feeds, then commits and pushes.
#
# Push recovery mirrors local_master_update.sh's strategy: save the
# merged comics_$DATE.json, reset to origin/main, restore, regenerate,
# push once. No git pull --rebase.

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$REPO_DIR"

LOG_FILE="$REPO_DIR/logs/pass2_update.log"
mkdir -p "$REPO_DIR/logs"

# Rotate log if it exceeds 10MB
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0) -gt 10485760 ]; then
    mv "$LOG_FILE" "$LOG_FILE.prev"
fi

exec > >(tee -a "$LOG_FILE") 2>&1

echo "================================================================================"
echo "ComicCaster Pass 2 Update (GoComics only) - $(date)"
echo "================================================================================"

FAILURES=()

# Load environment variables (.env has GoComics credentials)
if [ -f "$REPO_DIR/.env" ]; then
    export $(grep -v '^#' "$REPO_DIR/.env" | xargs)
fi

source "$REPO_DIR/venv/bin/activate"
pip install -e "$REPO_DIR" > /dev/null 2>&1 || true

# Load SSH key from Keychain (LaunchD runs without GUI session)
ssh-add --apple-use-keychain ~/.ssh/id_rsa 2>/dev/null || true

if ! ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "❌ GitHub SSH authentication failed - check SSH key and keychain"
    osascript -e 'display notification "Pass 2: SSH auth failed" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    echo "Aborting: Cannot push without SSH access."
    exit 0
fi

DATE_STR=$(date +%Y-%m-%d)
echo ""
echo "📅 Target date: $DATE_STR"

# Reset to origin/main before starting. Any uncommitted work or divergent
# local commits will be discarded — same policy as the master script.
git fetch origin
git reset --hard origin/main

PASS1_FILE="$REPO_DIR/data/comics_$DATE_STR.json"
if [ -f "$PASS1_FILE" ]; then
    PASS1_COUNT=$(python -c "import json; print(len(json.load(open('$PASS1_FILE'))))" 2>/dev/null || echo "?")
    echo "📂 Pass 1 produced $PASS1_COUNT comics today; pass 2 will merge into this"
else
    echo "⚠️  No pass 1 file at $PASS1_FILE — pass 2 will create it from scratch"
fi

echo ""
echo "=== Phase 1: GoComics re-scrape with merge ==="
if python scripts/authenticated_scraper_secure.py --output-dir ./data --merge; then
    echo "✅ GoComics pass-2 scrape complete"
else
    echo "❌ GoComics pass-2 scrape failed"
    FAILURES+=("GoComics pass-2 scrape")
fi

# If the scrape failed but the existing file is intact, generator can still
# run on pass-1 data (no harm, no change). If both failed, no commit happens.
echo ""
echo "=== Phase 2: GoComics feed regeneration ==="
if python scripts/generate_gocomics_feeds.py; then
    echo "✅ GoComics feeds regenerated"
else
    echo "❌ GoComics feed generation failed"
    FAILURES+=("GoComics feed generation")
fi

echo ""
echo "=== Phase 3: Commit and push ==="

# push_with_watchdog: same pattern as master script.
push_with_watchdog() {
    ( exec git push origin main ) &
    local PUSH_PID=$!
    ( sleep 60 && pkill -TERM -P $PUSH_PID 2>/dev/null; kill -TERM $PUSH_PID 2>/dev/null; sleep 2; pkill -KILL -P $PUSH_PID 2>/dev/null; kill -KILL $PUSH_PID 2>/dev/null ) &
    local TIMER_PID=$!
    if wait $PUSH_PID 2>/dev/null; then
        kill $TIMER_PID 2>/dev/null; wait $TIMER_PID 2>/dev/null
        return 0
    else
        kill $TIMER_PID 2>/dev/null; wait $TIMER_PID 2>/dev/null
        return 1
    fi
}

git add -f "data/comics_$DATE_STR.json" public/feeds/*.xml

if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit (pass 2 found nothing new)"
else
    git commit -m "Pass 2 GoComics feed update for $DATE_STR

Captures late-publishing political cartoonists missed by the 03:20 PT
pass-1 scrape. See docs/solutions/logic-errors/gocomics-favorites-page-timing.md."

    PUSH_OK=false
    if push_with_watchdog; then
        echo "✅ Successfully pushed pass-2 updates"
        PUSH_OK=true
    else
        echo "⚠️  First push attempt failed. Engaging reset-regenerate recovery..."

        # Pass 2 only touches data/comics_$DATE.json. Save it and the
        # GoComics feeds we just regenerated; reset; restore the JSON;
        # regenerate; push once.
        STAGING=$(mktemp -d)
        echo "📦 Staging pass-2 scrape data to $STAGING"
        if [ -f "$PASS1_FILE" ]; then
            cp -p "$PASS1_FILE" "$STAGING/"
            echo "  saved $(basename "$PASS1_FILE")"
        fi

        git fetch origin
        git reset --hard origin/main

        echo "📦 Restoring saved pass-2 scrape data"
        for f in "$STAGING"/*.json; do
            [ -f "$f" ] || continue
            cp -p "$f" "data/$(basename "$f")"
            echo "  restored $(basename "$f")"
        done

        echo "🔧 Regenerating GoComics feeds from restored scrape data"
        python scripts/generate_gocomics_feeds.py || FAILURES+=("GoComics regen in pass-2 recovery")

        git add -f "data/comics_$DATE_STR.json" public/feeds/*.xml
        if git diff --staged --quiet; then
            echo "ℹ️  No changes after regeneration; nothing more to push"
            PUSH_OK=true
        else
            git commit -m "Pass 2 GoComics feed update for $DATE_STR (recovery after push conflict)"
            if push_with_watchdog; then
                echo "✅ Successfully pushed pass-2 recovery commit"
                PUSH_OK=true
            else
                echo "❌ Pass-2 recovery push also failed. Tomorrow's pass 1 will retry."
            fi
        fi

        rm -rf "$STAGING"
    fi

    if [ "$PUSH_OK" = false ]; then
        FAILURES+=("Git push")
    fi
fi

echo ""
echo "================================================================================"
if [ ${#FAILURES[@]} -eq 0 ]; then
    echo "ComicCaster Pass 2 Complete (ALL SUCCESS) - $(date)"
    osascript -e 'display notification "Pass 2 GoComics update complete" with title "ComicCaster: Pass 2" sound name "Glass"' 2>/dev/null || true
else
    FAIL_LIST=$(IFS=', '; echo "${FAILURES[*]}")
    echo "ComicCaster Pass 2 Complete with FAILURES - $(date)"
    echo "Failed steps: $FAIL_LIST"
    osascript -e "display notification \"Pass 2 failed: $FAIL_LIST\" with title \"ComicCaster: Pass 2 Failure\" sound name \"Basso\"" 2>/dev/null || true
fi
echo "================================================================================"

# Always exit 0 — LaunchD should not retry on failure.
exit 0
