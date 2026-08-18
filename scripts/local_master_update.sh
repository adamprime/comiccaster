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

# Track failures. FAILURES holds human-readable labels for the log summary and
# the desktop notification; FAILED_KEYS holds stable "<slug>:<kind>" slugs for
# the GitHub issue reporter. Only scrape, invariant, and push failures get a
# slug -- feed generation and git fetch stay log-only by design.
FAILURES=()
FAILED_KEYS=()

# Sources this run examines, so the reporter knows what it may auto-close.
# Pass 1 covers everything; Pass 2 covers GoComics only.
# `preflight` is included because reaching the end of a run proves it passed,
# which is what auto-closes a preflight issue from a previous run.
ALERT_COVERED="gocomics,comicskingdom,tinyview,newyorker,farside,creators,mrboffo,push,preflight,cksession,branch,autologin"

# Load environment variables (.env has GoComics credentials)
if [ -f "$REPO_DIR/.env" ]; then
    export $(grep -v '^#' "$REPO_DIR/.env" | xargs)
fi

# Activate virtual environment
source "$REPO_DIR/venv/bin/activate"

# Install comiccaster package in editable mode (if not already installed)
pip install -e "$REPO_DIR" > /dev/null 2>&1 || true

# Report this run's outcome by dispatching a GitHub Actions workflow rather than
# creating issues here. The Mini's `gh` is authenticated as the repo owner, and
# GitHub sends NO notification for an issue you author yourself -- host-created
# alerts were silently invisible to the person meant to act on them. Dispatching
# makes github-actions[bot] the author, which does notify.
#
# This is a direct API call, not a git push, so it still fires when pushing is
# the thing that broke. Best-effort: never fatal to the pipeline.
report_pipeline_failures() {
    local covered="$1" failed="$2"
    gh workflow run pipeline-alert.yml \
        --field run=pass1 \
        --field date="$(date +%Y-%m-%d)" \
        --field covered="$covered" \
        --field failed="$failed" || true
}

# Verify GitHub SSH access before proceeding.
# Derive the SSH host from the actual push remote so this check can never drift
# from what the push uses. The remote uses a dedicated host alias
# (git@github-comiccaster:...) whose deploy key is named via IdentityFile in
# ~/.ssh/config, so no ssh-agent/keychain load is required. Testing a hardcoded
# git@github.com here was a false-negative source: it validated the wrong host
# and aborted the whole run even though the aliased push would have succeeded.
REMOTE_URL="$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null)"
SSH_HOST="$(echo "$REMOTE_URL" | sed -n 's/^git@\([^:]*\):.*/\1/p')"
if [ -z "$SSH_HOST" ]; then
    echo "❌ Could not determine SSH host from origin remote: '$REMOTE_URL'"
    echo "Aborting: Cannot push without a resolvable SSH remote."
    # This aborts before any scraping, so the normal end-of-run report never
    # happens. Alert here or the hardest failure is the quietest one.
    report_pipeline_failures "preflight" "preflight:remote"
    echo "================================================================================"
    echo "ComicCaster Master Update ABORTED (SSH) - $(date)"
    echo "================================================================================"
    exit 0
fi
if ! ssh -T "$SSH_HOST" 2>&1 | grep -q "successfully authenticated"; then
    echo "❌ GitHub SSH authentication failed ($SSH_HOST) - check SSH key and keychain"
    osascript -e 'display notification "SSH auth failed - check keychain" with title "ComicCaster: Error" sound name "Basso"' 2>/dev/null || true
    # This is fatal -- we can't push anything without SSH
    echo "Aborting: Cannot push without SSH access."
    # Aborts before any scraping, so alert here (see PR #168 -- a preflight bug
    # silently killed daily runs).
    report_pipeline_failures "preflight" "preflight:ssh"
    echo "================================================================================"
    echo "ComicCaster Master Update ABORTED (SSH) - $(date)"
    echo "================================================================================"
    exit 0  # Exit 0 so LaunchD doesn't retry endlessly
fi
echo "✅ GitHub SSH authentication verified"

# Branch guard.
# The LaunchAgents fire regardless of what is checked out, and everything below
# assumes main: the sync resets --hard to origin/main, and Phase 3 pushes the
# local `main` ref. Run this on any other branch and the failure is SILENT --
# the reset moves the *feature branch* pointer, the commit lands on that branch,
# and `git push origin main` pushes an unchanged main and reports "Everything
# up-to-date" as success. That is exactly what happened on 2026-07-28: a full
# Pass 2 feed update never reached subscribers and the run declared ALL SUCCESS.
#
# Switch back to main rather than abort, so a forgotten checkout costs a warning
# instead of a day of stale feeds. Deliberately NOT `checkout -f`: discarding
# someone's uncommitted branch work is worse than skipping a run, so a checkout
# that cannot proceed aborts loudly instead.
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Repo is on '$CURRENT_BRANCH', not main -- switching before syncing"
    if git checkout main; then
        echo "✅ Switched to main (was on '$CURRENT_BRANCH')"
        FAILURES+=("repo was left on branch '$CURRENT_BRANCH'")
        FAILED_KEYS+=("branch:wrongbranch")
    else
        echo "❌ Could not switch to main from '$CURRENT_BRANCH' -- aborting"
        echo "   Refusing to reset --hard while on another branch."
        report_pipeline_failures "branch" "branch:checkout"
        echo "ComicCaster ABORTED (wrong branch) - $(date)"
        exit 0
    fi
fi

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
echo "[1/7] Scraping GoComics (authenticated)..."
if python scripts/authenticated_scraper_secure.py --output-dir ./data; then
    echo "✅ GoComics scraping succeeded"
else
    echo "❌ GoComics scraping failed"
    FAILURES+=("GoComics scraping")
    FAILED_KEYS+=("gocomics:scrape")
fi

echo ""
echo "[2/7] Scraping Comics Kingdom..."
# CK_SCRAPER_EXTRA_ARGS lets host-specific wrappers inject flags (e.g. the
# Mini sets --show-browser because upstream anti-bot blocks headless Chrome).
# Intentionally unquoted for word-splitting; supports single-token args.
if python scripts/comicskingdom_scraper_individual.py ${CK_SCRAPER_EXTRA_ARGS:-} --date "$DATE_STR" --output-dir data; then
    echo "✅ Comics Kingdom scraping succeeded"
else
    echo "❌ Comics Kingdom scraping failed"
    FAILURES+=("Comics Kingdom scraping")
    FAILED_KEYS+=("comicskingdom:scrape")
fi

echo ""
echo "[3/7] Scraping TinyView..."
if python scripts/tinyview_scraper_local_authenticated.py --date "$DATE_STR" --days-back 90; then
    echo "✅ TinyView scraping succeeded"
else
    echo "❌ TinyView scraping failed"
    FAILURES+=("TinyView scraping")
    FAILED_KEYS+=("tinyview:scrape")
fi

echo ""
echo "[4/7] Scraping Far Side..."
if python scripts/scrape_farside.py; then
    echo "✅ Far Side scraping succeeded"
else
    echo "❌ Far Side scraping failed"
    FAILURES+=("Far Side scraping")
    FAILED_KEYS+=("farside:scrape")
fi

echo ""
echo "[5/7] Scraping New Yorker Daily Cartoon..."
if python scripts/scrape_newyorker.py; then
    echo "✅ New Yorker scraping succeeded"
else
    echo "❌ New Yorker scraping failed"
    FAILURES+=("New Yorker scraping")
    FAILED_KEYS+=("newyorker:scrape")
fi

echo ""
echo "[6/7] Scraping Creators Syndicate..."
if python scripts/scrape_creators.py; then
    echo "✅ Creators scraping succeeded"
else
    echo "❌ Creators scraping failed"
    FAILURES+=("Creators scraping")
    FAILED_KEYS+=("creators:scrape")
fi

echo ""
echo "[7/7] Scraping Mr. Boffo..."
if python scripts/scrape_mrboffo.py; then
    echo "✅ Mr. Boffo scraping succeeded"
else
    echo "❌ Mr. Boffo scraping failed"
    FAILURES+=("Mr. Boffo scraping")
    FAILED_KEYS+=("mrboffo:scrape")
fi

# Phase 2: Generate all feeds from scraped data
# Run all generators regardless of scraper results -- they use whatever data exists
echo ""
echo "=== Phase 2: Generating All Feeds ==="

echo ""
echo "[1/7] Generating GoComics feeds (from scraped data)..."
if python scripts/generate_gocomics_feeds.py; then
    echo "✅ GoComics feed generation succeeded"
else
    echo "❌ GoComics feed generation failed"
    FAILURES+=("GoComics feed generation")
fi

echo ""
echo "[2/7] Generating Comics Kingdom feeds..."
if python scripts/generate_comicskingdom_feeds.py; then
    echo "✅ Comics Kingdom feed generation succeeded"
else
    echo "❌ Comics Kingdom feed generation failed"
    FAILURES+=("Comics Kingdom feed generation")
fi

echo ""
echo "[3/7] Generating TinyView feeds..."
if python scripts/generate_tinyview_feeds_from_data.py; then
    echo "✅ TinyView feed generation succeeded"
else
    echo "❌ TinyView feed generation failed"
    FAILURES+=("TinyView feed generation")
fi

echo ""
echo "[4/7] Generating New Yorker feed..."
if python scripts/generate_newyorker_feeds.py; then
    echo "✅ New Yorker feed generation succeeded"
else
    echo "❌ New Yorker feed generation failed"
    FAILURES+=("New Yorker feed generation")
fi

echo ""
echo "[5/7] Generating Far Side feeds..."
if python scripts/generate_farside_feeds.py; then
    echo "✅ Far Side feed generation succeeded"
else
    echo "❌ Far Side feed generation failed"
    FAILURES+=("Far Side feed generation")
fi

echo ""
echo "[6/7] Generating Creators feeds..."
if python scripts/generate_creators_feeds.py; then
    echo "✅ Creators feed generation succeeded"
else
    echo "❌ Creators feed generation failed"
    FAILURES+=("Creators feed generation")
fi

echo ""
echo "[7/7] Generating Mr. Boffo feed..."
if python scripts/generate_mrboffo_feeds.py; then
    echo "✅ Mr. Boffo feed generation succeeded"
else
    echo "❌ Mr. Boffo feed generation failed"
    FAILURES+=("Mr. Boffo feed generation")
fi

# Invariant guard: if a scraper reported success, its daily data file must exist.
# Catches silent regressions where a scraper exits 0 but skipped writing output.
# Violations surface as additional FAILURES entries; the pipeline still commits
# and pushes whatever did succeed.
echo ""
echo "=== Verifying scrape invariants ==="
check_scrape_output() {
    local source="$1" slug="$2" file="$3"
    # Skip the check if this source's scraping was already reported as failed.
    if [ ${#FAILURES[@]} -gt 0 ] && printf '%s\n' "${FAILURES[@]}" | grep -qxF "$source scraping"; then
        return 0
    fi
    if [ ! -f "$file" ]; then
        echo "❌ Invariant violation: $source scrape reported success but $file is missing"
        FAILURES+=("$source invariant ($(basename "$file") missing)")
        # Far Side is checked twice; a duplicate slug collapses to one issue.
        FAILED_KEYS+=("$slug:invariant")
    else
        echo "✅ $source: $(basename "$file") present"
        # Existence is not enough. A scrape can run, write a well-formed file
        # and put nothing in it: on 2026-08-03 TinyView wrote `[]` and the run
        # still reported ALL SUCCESS. Nothing surfaced it either, because the
        # generator builds feeds from a 90-day window, so a missing day looks
        # like a healthy feed one entry short. Assert a plausible entry count.
        if ! python scripts/check_scrape_counts.py "$file"; then
            FAILURES+=("$source empty or partial scrape")
            FAILED_KEYS+=("$slug:invariant")
        fi
    fi
}
check_scrape_output "GoComics"       "gocomics"      "data/comics_$DATE_STR.json"
check_scrape_output "Comics Kingdom" "comicskingdom" "data/comicskingdom_$DATE_STR.json"
check_scrape_output "TinyView"       "tinyview"      "data/tinyview_$DATE_STR.json"
check_scrape_output "New Yorker"     "newyorker"     "data/newyorker_$DATE_STR.json"
check_scrape_output "Far Side"       "farside"       "data/farside_daily_$DATE_STR.json"
check_scrape_output "Far Side"       "farside"       "data/farside_new_$DATE_STR.json"
check_scrape_output "Creators"       "creators"      "data/creators_$DATE_STR.json"
check_scrape_output "Mr. Boffo"      "mrboffo"       "data/mrboffo_$DATE_STR.json"

# Comics Kingdom session expiry check.
# Reports the cookie's expiry, which is NOT session health -- two independent
# clocks. CK rolls the cookie expiry forward on any visit (even ones it redirects
# to login), while the server-side session dies ~7 days after *login* regardless
# of traffic. So a green line here is not evidence the session works (2026-08-05:
# it read "7.0 days remaining" during the run where CK rejected the scraper).
# The scrape itself is the real auth check. What this genuinely catches is a
# *missing* token, which is unambiguous (2026-08-18, issue #188).
# `cksession` is in ALERT_COVERED, so the alert clears itself after a good reauth.
echo ""
echo "=== Checking Comics Kingdom session expiry ==="
if python scripts/check_ck_session.py; then
    :
else
    FAILURES+=("Comics Kingdom session expiring")
    FAILED_KEYS+=("cksession:expiry")
fi

# Host auto-login / remote-access config check.
# The LaunchAgents that run this pipeline load only on GUI login, and macOS
# updates have been known to reset login settings. The drift is invisible until
# the next reboot -- by which point the box is at the login window with no
# Tailscale, so it cannot be fixed remotely (2026-08-01 outage, 25h). Between
# the drift and that reboot the machine is still reachable and the fix takes a
# minute, so surface it now. `autologin` is in ALERT_COVERED, so the alert
# clears itself once the setting is restored.
# No detail is passed to the reporter on purpose: the findings describe the
# host's security posture and the issue it opens is public.
echo ""
echo "=== Checking host auto-login configuration ==="
if python scripts/check_host_config.py; then
    :
else
    FAILURES+=("Host configuration drifted")
    FAILED_KEYS+=("autologin:config")
fi

# Phase 3: Commit and push everything that succeeded.
# Recovery on push rejection: save same-day scrape JSONs to a staging dir, reset
# to origin/main, restore the JSONs, re-run all data-driven generators, and
# push once. All seven sources are data-driven, so recovery is a full
# regeneration — no source gets stale on recovery. Deliberately avoids git
# pull --rebase against generated XML artifacts, which explodes into hundreds
# of conflicts (see 2026-04-17 incident).
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

# verify_push_landed: confirm the commit we just made is genuinely reachable from
# origin/main. `git push` exiting 0 is NOT proof of publication -- pushing a ref
# that has nothing new prints "Everything up-to-date" and succeeds, which on
# 2026-07-28 turned an unpublished feed update into a reported ALL SUCCESS.
# Fetch first so origin/main reflects the remote rather than a stale local ref.
verify_push_landed() {
    if ! git fetch -q origin main 2>/dev/null; then
        echo "⚠️  Could not fetch to verify the push landed"
        return 1
    fi
    if git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
        echo "✅ Verified: $(git rev-parse --short HEAD) is on origin/main"
        return 0
    fi
    echo "❌ Push reported success but $(git rev-parse --short HEAD) is NOT on origin/main"
    return 1
}

git add -f data/*.json public/feeds/*.xml

if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    git commit -m "Update all comic feeds for $DATE_STR

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"

    PUSH_OK=false
    if push_with_watchdog && verify_push_landed; then
        echo "✅ Successfully pushed all updates"
        PUSH_OK=true
    else
        echo "⚠️  First push attempt failed. Engaging reset-regenerate recovery..."

        # Save today's scrape data files. These are authoritative pipeline inputs
        # and the one piece of state we cannot recreate without re-scraping.
        # Far Side daily scrapes the site's 3-day serving window each run, so we
        # preserve all three target-date snapshots our scrape produced.
        STAGING=$(mktemp -d)
        echo "📦 Staging same-day scrape data to $STAGING"
        FS_YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(days=1)).isoformat())")
        FS_DAYBEFORE=$(date -v-2d +%Y-%m-%d 2>/dev/null || python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(days=2)).isoformat())")
        for f in \
            "data/comics_$DATE_STR.json" \
            "data/comicskingdom_$DATE_STR.json" \
            "data/tinyview_$DATE_STR.json" \
            "data/newyorker_$DATE_STR.json" \
            "data/farside_daily_$DATE_STR.json" \
            "data/farside_daily_$FS_YESTERDAY.json" \
            "data/farside_daily_$FS_DAYBEFORE.json" \
            "data/farside_new_$DATE_STR.json" \
            "data/creators_$DATE_STR.json" \
            "data/mrboffo_$DATE_STR.json"; do
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

        # Regenerate every feed from restored data. All seven sources are now
        # data-driven (see 3a/3b/3c refactors), so recovery produces
        # byte-identical output to a clean run from the same scrape data.
        echo "🔧 Regenerating feeds from restored scrape data"
        python scripts/generate_gocomics_feeds.py           || FAILURES+=("GoComics regen in recovery")
        python scripts/generate_comicskingdom_feeds.py      || FAILURES+=("Comics Kingdom regen in recovery")
        python scripts/generate_tinyview_feeds_from_data.py || FAILURES+=("TinyView regen in recovery")
        python scripts/generate_newyorker_feeds.py          || FAILURES+=("New Yorker regen in recovery")
        python scripts/generate_farside_feeds.py            || FAILURES+=("Far Side regen in recovery")
        python scripts/generate_creators_feeds.py           || FAILURES+=("Creators regen in recovery")
        python scripts/generate_mrboffo_feeds.py            || FAILURES+=("Mr. Boffo regen in recovery")

        git add -f data/*.json public/feeds/*.xml
        if git diff --staged --quiet; then
            echo "ℹ️  No changes after regeneration; nothing more to push"
            PUSH_OK=true
        else
            git commit -m "Update comic feeds for $DATE_STR (recovery after push conflict)

Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"

            if push_with_watchdog && verify_push_landed; then
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
        FAILED_KEYS+=("push:verification")
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

# Reconcile GitHub issues. Runs on success too -- that is what closes an issue
# for a source that has recovered.
FAILED_KEY_LIST=""
if [ ${#FAILED_KEYS[@]} -gt 0 ]; then
    FAILED_KEY_LIST=$(IFS=,; echo "${FAILED_KEYS[*]}")
fi
report_pipeline_failures "$ALERT_COVERED" "$FAILED_KEY_LIST"
echo "================================================================================"

# Always exit 0 -- LaunchD should not retry on failure.
# The daily schedule will run it again tomorrow.
# If something needs immediate attention, the notification tells you.
exit 0
