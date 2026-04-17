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

# Sync local main with origin.
# Policy: local main must exactly match origin/main at the start of each run.
# Any uncommitted work or divergent local commits will be discarded — this is
# deliberate. Recovery from push conflicts also uses reset+regenerate rather
# than merge/rebase (see Phase 3).
echo ""
echo "Syncing local main with origin..."
if git fetch --all --prune; then
    git reset --hard origin/main
    git gc --prune=now 2>/dev/null || true
else
    echo "⚠️  git fetch failed; proceeding with current local state"
    FAILURES+=("git fetch at start")
fi

# Phase 1: Scrape all sources (sequential for reliability)
echo ""
echo "=== Phase 1: Scraping All Sources ==="
DATE_STR=$(date +%Y-%m-%d)

echo ""
echo "[1/6] Scraping GoComics (authenticated)..."
if python scripts/authenticated_scraper_secure.py --output-dir ./data; then
    echo "✅ GoComics scraping succeeded"
else
    echo "❌ GoComics scraping failed"
    FAILURES+=("GoComics scraping")
fi

echo ""
echo "[2/6] Scraping Comics Kingdom..."
# CK_SCRAPER_EXTRA_ARGS lets host-specific wrappers inject flags (e.g. the
# Mini sets --show-browser because upstream anti-bot blocks headless Chrome).
# Intentionally unquoted for word-splitting; supports single-token args.
if python scripts/comicskingdom_scraper_individual.py ${CK_SCRAPER_EXTRA_ARGS:-} --date "$DATE_STR" --output-dir data; then
    echo "✅ Comics Kingdom scraping succeeded"
else
    echo "❌ Comics Kingdom scraping failed"
    FAILURES+=("Comics Kingdom scraping")
fi

echo ""
echo "[3/6] Scraping TinyView..."
if python scripts/tinyview_scraper_local_authenticated.py --date "$DATE_STR" --days-back 90; then
    echo "✅ TinyView scraping succeeded"
else
    echo "❌ TinyView scraping failed"
    FAILURES+=("TinyView scraping")
fi

echo ""
echo "[4/6] Scraping Far Side..."
if python scripts/scrape_farside.py; then
    echo "✅ Far Side scraping succeeded"
else
    echo "❌ Far Side scraping failed"
    FAILURES+=("Far Side scraping")
fi

echo ""
echo "[5/6] Scraping New Yorker Daily Cartoon..."
if python scripts/scrape_newyorker.py; then
    echo "✅ New Yorker scraping succeeded"
else
    echo "❌ New Yorker scraping failed"
    FAILURES+=("New Yorker scraping")
fi

echo ""
echo "[6/6] Scraping Creators Syndicate..."
if python scripts/scrape_creators.py; then
    echo "✅ Creators scraping succeeded"
else
    echo "❌ Creators scraping failed"
    FAILURES+=("Creators scraping")
fi

# Phase 2: Generate all feeds from scraped data
# Run all generators regardless of scraper results -- they use whatever data exists
echo ""
echo "=== Phase 2: Generating All Feeds ==="

echo ""
echo "[1/6] Generating GoComics feeds (from scraped data)..."
if python scripts/generate_gocomics_feeds.py; then
    echo "✅ GoComics feed generation succeeded"
else
    echo "❌ GoComics feed generation failed"
    FAILURES+=("GoComics feed generation")
fi

echo ""
echo "[2/6] Generating Comics Kingdom feeds..."
if python scripts/generate_comicskingdom_feeds.py; then
    echo "✅ Comics Kingdom feed generation succeeded"
else
    echo "❌ Comics Kingdom feed generation failed"
    FAILURES+=("Comics Kingdom feed generation")
fi

echo ""
echo "[3/6] Generating TinyView feeds..."
if python scripts/generate_tinyview_feeds_from_data.py; then
    echo "✅ TinyView feed generation succeeded"
else
    echo "❌ TinyView feed generation failed"
    FAILURES+=("TinyView feed generation")
fi

echo ""
echo "[4/6] Generating New Yorker feed..."
if python scripts/generate_newyorker_feeds.py; then
    echo "✅ New Yorker feed generation succeeded"
else
    echo "❌ New Yorker feed generation failed"
    FAILURES+=("New Yorker feed generation")
fi

echo ""
echo "[5/6] Generating Far Side feeds..."
if python scripts/generate_farside_feeds.py; then
    echo "✅ Far Side feed generation succeeded"
else
    echo "❌ Far Side feed generation failed"
    FAILURES+=("Far Side feed generation")
fi

echo ""
echo "[6/6] Generating Creators feeds..."
if python scripts/generate_creators_feeds.py; then
    echo "✅ Creators feed generation succeeded"
else
    echo "❌ Creators feed generation failed"
    FAILURES+=("Creators feed generation")
fi

# Invariant guard: if a scraper reported success, its daily data file must exist.
# Catches silent regressions where a scraper exits 0 but skipped writing output.
# Violations surface as additional FAILURES entries; the pipeline still commits
# and pushes whatever did succeed.
echo ""
echo "=== Verifying scrape invariants ==="
check_scrape_output() {
    local source="$1" file="$2"
    # Skip the check if this source's scraping was already reported as failed.
    if [ ${#FAILURES[@]} -gt 0 ] && printf '%s\n' "${FAILURES[@]}" | grep -qxF "$source scraping"; then
        return 0
    fi
    if [ ! -f "$file" ]; then
        echo "❌ Invariant violation: $source scrape reported success but $file is missing"
        FAILURES+=("$source invariant ($(basename "$file") missing)")
    else
        echo "✅ $source: $(basename "$file") present"
    fi
}
check_scrape_output "GoComics"       "data/comics_$DATE_STR.json"
check_scrape_output "Comics Kingdom" "data/comicskingdom_$DATE_STR.json"
check_scrape_output "TinyView"       "data/tinyview_$DATE_STR.json"
check_scrape_output "New Yorker"     "data/newyorker_$DATE_STR.json"
check_scrape_output "Far Side"       "data/farside_daily_$DATE_STR.json"
check_scrape_output "Far Side"       "data/farside_new_$DATE_STR.json"
check_scrape_output "Creators"       "data/creators_$DATE_STR.json"

# Phase 3: Commit and push everything that succeeded.
# Recovery on push rejection: save same-day scrape JSONs to a staging dir, reset
# to origin/main, restore the JSONs, re-run data-driven generators, and push
# once. Deliberately avoids git pull --rebase against generated XML artifacts,
# which explodes into hundreds of conflicts (see 2026-04-17 incident).
echo ""
echo "=== Phase 3: Committing and Pushing ==="

# push_with_watchdog: attempts `git push origin main` with a 60s timeout that
# kills the push and all its descendants. Returns 0 on success, nonzero on
# failure (rejection, timeout, network error).
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

git add -f data/*.json public/feeds/*.xml

if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    git commit -m "Update all comic feeds for $DATE_STR

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"

    PUSH_OK=false
    if push_with_watchdog; then
        echo "✅ Successfully pushed all updates"
        PUSH_OK=true
    else
        echo "⚠️  First push attempt failed. Engaging reset-regenerate recovery..."

        # Save today's scrape data files. These are authoritative pipeline inputs
        # and the one piece of state we cannot recreate without re-scraping.
        STAGING=$(mktemp -d)
        echo "📦 Staging same-day scrape data to $STAGING"
        for f in \
            "data/comics_$DATE_STR.json" \
            "data/comicskingdom_$DATE_STR.json" \
            "data/tinyview_$DATE_STR.json" \
            "data/newyorker_$DATE_STR.json"; do
            if [ -f "$f" ]; then
                cp -p "$f" "$STAGING/"
                echo "  saved $(basename "$f")"
            fi
        done

        # Pick up whatever landed on origin.
        git fetch origin
        git reset --hard origin/main

        # Restore saved scrape data on top of the reset state.
        echo "📦 Restoring saved scrape data"
        for f in "$STAGING"/*.json; do
            [ -f "$f" ] || continue
            cp -p "$f" "data/$(basename "$f")"
            echo "  restored $(basename "$f")"
        done

        # Regenerate data-driven feeds. New Yorker, Far Side, and Creators are
        # not regenerated here — their feeds stay at origin state until the
        # 3a/3b/3c refactors make them data-driven.
        echo "🔧 Regenerating feeds from restored scrape data"
        python scripts/generate_gocomics_feeds.py         || FAILURES+=("GoComics regen in recovery")
        python scripts/generate_comicskingdom_feeds.py    || FAILURES+=("Comics Kingdom regen in recovery")
        python scripts/generate_tinyview_feeds_from_data.py || FAILURES+=("TinyView regen in recovery")

        git add -f data/*.json public/feeds/*.xml
        if git diff --staged --quiet; then
            echo "ℹ️  No changes after regeneration; nothing more to push"
            PUSH_OK=true
        else
            git commit -m "Update comic feeds for $DATE_STR (recovery after push conflict)

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"

            if push_with_watchdog; then
                echo "✅ Successfully pushed recovery commit"
                PUSH_OK=true
            else
                echo "❌ Recovery push also failed. Bailing; tomorrow's run will retry."
            fi
        fi

        rm -rf "$STAGING"
    fi

    if [ "$PUSH_OK" = false ]; then
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
