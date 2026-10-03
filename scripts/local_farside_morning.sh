#!/bin/bash
# Far Side morning pass: ship today's Daily Dose on the first slot that finds it.
#
# thefarside.com publishes its Daily Dose at an unpredictable hour, often after
# the 03:20 Pass 1 scrape. A LaunchAgent (com.comiccaster.farside) fires this
# every 30 minutes from 03:30 to 12:00. Each firing is one "slot":
#
#   1. Fetch refs only. If today's dose is already on origin/main and passes the
#      count guard, log "already-shipped" and stop.
#   2. Scrape today's Daily Dose only. Not published yet, or not yet the full
#      5 strips (2 at weekends): log it and stop. The next slot retries.
#   3. Otherwise, if the operator's checkout is safe to sync (see
#      farside_morning.py safe-sync), reset to origin/main, regenerate the Far
#      Side feeds, commit exactly two paths, push, and report success, which
#      closes any open Far Side issue.
#
# Only the final (noon) slot raises an alert, and it ships any dose the count
# guard accepts. Every slot appends its outcome to logs/farside_morning_slots.log,
# which is how the site's real publish time is measured.
#
# No step before the safe-sync check touches the checkout beyond fetching refs
# and writing today's daily file: this runs during working hours, in the
# operator's checkout. Every decision lives in scripts/farside_morning.py, which
# is unit-tested; this file only sequences git, the scraper and the generator.
#
# Like the other passes: no `set -e` (an unpublished date and several git probes
# exit nonzero in normal operation), each step's status is handled explicitly,
# and the script always exits 0 so launchd never retries.

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$REPO_DIR"

LOG_FILE="$REPO_DIR/logs/farside_morning.log"
mkdir -p "$REPO_DIR/logs"

PY="$REPO_DIR/venv/bin/python"
HELPER="$REPO_DIR/scripts/farside_morning.py"

# Which slot is this? Decided before the lock, because the noon slot waits for
# the lock (a long catch-up run must not swallow the day's only alert) while
# earlier slots give way to whatever holds it.
SLOT_OUT="$("$PY" "$HELPER" slot)"
SLOT_DATE="$(printf '%s\n' "$SLOT_OUT" | sed -n 's/^SLOT_DATE=//p')"
SLOT_FINAL="$(printf '%s\n' "$SLOT_OUT" | sed -n 's/^SLOT_FINAL=//p')"
if [ -z "$SLOT_DATE" ] || [ -z "$SLOT_FINAL" ]; then
    echo "$(date) - Far Side morning slot could not determine its date; helper said: $SLOT_OUT" >> "$LOG_FILE"
    exit 0
fi

log_slot() {
    "$PY" "$HELPER" log --date "$SLOT_DATE" --outcome "$1" --count "${2:-0}" \
        || echo "⚠️  Could not append to the slot log"
}

# Shared pipeline lock; see local_master_update.sh for the rationale.
if [ -z "${PIPELINE_LOCK_HELD:-}" ]; then
    LOCK_WAIT=0
    [ "$SLOT_FINAL" = "1" ] && LOCK_WAIT=1800
    PIPELINE_LOCK_HELD=1 /usr/bin/lockf -s -k -t "$LOCK_WAIT" "$REPO_DIR/logs/pipeline.lock" \
        /bin/bash "$REPO_DIR/scripts/$(basename "${BASH_SOURCE[0]}")" "$@"
    lock_rc=$?
    if [ "$lock_rc" -eq 75 ]; then
        echo "$(date) - Far Side morning slot skipped: another pipeline run holds the lock" >> "$LOG_FILE"
        log_slot lock-busy 0
    fi
    exit 0
fi

# Rotate log if it exceeds 10MB
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0) -gt 10485760 ]; then
    mv "$LOG_FILE" "$LOG_FILE.prev"
fi

exec > >(tee -a "$LOG_FILE") 2>&1

echo "================================================================================"
echo "Far Side morning slot - $(date) - Daily Dose $SLOT_DATE (final slot: $SLOT_FINAL)"
echo "================================================================================"

DAILY="data/farside_daily_$SLOT_DATE.json"
FINAL_ARGS=()
[ "$SLOT_FINAL" = "1" ] && FINAL_ARGS=(--final)

# Reports under run=farside-morning and covers `farside` only: this pass
# examines the Daily Dose and nothing else, so it must never close another
# source's issue, nor Pass 1's push/preflight/branch issues. Its own
# infrastructure failures are reported as farside:<kind> for the same reason.
report_pipeline_failures() {
    gh workflow run pipeline-alert.yml \
        --field run=farside-morning \
        --field date="$SLOT_DATE" \
        --field covered=farside \
        --field failed="$1" || true
}

# A slot that cannot ship stops here. Before noon it only logs; the next slot
# retries. The final slot logs "final-unshipped" and raises the day's alert.
stop_slot() {
    local outcome="$1" kind="$2" count="${3:-0}"
    if [ "$SLOT_FINAL" = "1" ]; then
        echo "❌ Final slot: today's Daily Dose has not shipped ($outcome)"
        log_slot final-unshipped "$count"
        report_pipeline_failures "farside:$kind"
    else
        echo "⏳ $outcome; the next slot will retry"
        log_slot "$outcome" "$count"
    fi
    echo "================================================================================"
    exit 0
}

# evaluate FILE [--final] -> sets DECISION and COUNT
evaluate() {
    local out
    out="$("$PY" "$HELPER" evaluate --file "$1" --date "$SLOT_DATE" "${@:2}")"
    DECISION="$(printf '%s\n' "$out" | sed -n 's/^DECISION=//p')"
    COUNT="$(printf '%s\n' "$out" | sed -n 's/^COUNT=//p')"
    [ -n "$DECISION" ] || DECISION=unshippable
    [ -n "$COUNT" ] || COUNT=0
}

# --- 1. Already shipped? ------------------------------------------------------
# Judged on origin/main, never on a local file: a local file can exist after a
# failed push. Refs only; the working tree is untouched.
if ! git fetch -q origin main 2>/dev/null; then
    stop_slot fetch-failed fetch
fi

# Judged with this slot's own finality: before noon, a short dose that Pass 1
# or a catch-up run committed is not yet the full dose, so it is re-scraped
# (safe-sync exempts and carries our own tracked daily file, so it can ship).
SHIPPED_COPY="$(mktemp)"
if git show "origin/main:$DAILY" > "$SHIPPED_COPY" 2>/dev/null; then
    evaluate "$SHIPPED_COPY" "${FINAL_ARGS[@]}"
    rm -f "$SHIPPED_COPY"
    if [ "$DECISION" = "ship" ]; then
        echo "✅ $DAILY is already on origin/main ($COUNT strips)"
        log_slot already-shipped "$COUNT"
        echo "================================================================================"
        exit 0
    fi
    echo "⚠️  origin/main has $DAILY but it is not yet a complete dose ($COUNT strips); re-scraping"
else
    rm -f "$SHIPPED_COPY"
fi

# --- 2. Scrape today's Daily Dose only ---------------------------------------
# Writes $DAILY only when the site has published the date; never touches other
# dates' files or New Stuff.
"$PY" scripts/scrape_farside.py --daily-only --date "$SLOT_DATE"

evaluate "$DAILY" "${FINAL_ARGS[@]}"
case "$DECISION" in
    ship) echo "✅ Daily Dose found: $COUNT strips" ;;
    incomplete) stop_slot incomplete incomplete "$COUNT" ;;
    *) stop_slot unpublished unpublished "$COUNT" ;;
esac

# --- 3. Ship ------------------------------------------------------------------
# SSH preflight first, so the safe-sync check sits immediately before the reset
# and the window in which an operator edit could be lost is as short as possible.
REMOTE_URL="$(git remote get-url origin 2>/dev/null)"
SSH_HOST="$(echo "$REMOTE_URL" | sed -n 's/^git@\([^:]*\):.*/\1/p')"
if [ -z "$SSH_HOST" ] || ! ssh -T "$SSH_HOST" 2>&1 | grep -q "successfully authenticated"; then
    echo "❌ GitHub SSH check failed for '${SSH_HOST:-$REMOTE_URL}'"
    stop_slot preflight-failed preflight "$COUNT"
fi

BRANCH="$(git branch --show-current)"
HEAD_IS_ANCESTOR=0
git merge-base --is-ancestor HEAD origin/main 2>/dev/null && HEAD_IS_ANCESTOR=1
# Capture git status before piping it: without pipefail a failing status would
# reach the helper as empty input, which reads as a clean checkout.
STATUS_OUT="$(git status --porcelain --untracked-files=no)"
STATUS_RC=$?
if [ "$STATUS_RC" -ne 0 ]; then
    echo "⏸  git status failed (exit $STATUS_RC); leaving the checkout untouched"
    stop_slot deferred-checkout checkout "$COUNT"
fi
SAFE_OUT="$(printf '%s' "$STATUS_OUT" \
    | "$PY" "$HELPER" safe-sync --date "$SLOT_DATE" --branch "$BRANCH" --head-is-ancestor "$HEAD_IS_ANCESTOR")"
if [ "$SAFE_OUT" != "SAFE=1" ]; then
    echo "⏸  Checkout is not safe to sync (${SAFE_OUT:-no verdict}); leaving it untouched"
    stop_slot deferred-checkout checkout "$COUNT"
fi

# The checkout is on main, holds no unpushed commits and no tracked changes but
# our own daily file, so resetting discards nothing of the operator's. Our file
# may be tracked (an invalid copy already on origin/main), so carry it across.
CARRY_DIR="$(mktemp -d)"
cp "$DAILY" "$CARRY_DIR/"
git reset -q --hard origin/main
cp "$CARRY_DIR/$(basename "$DAILY")" "$DAILY"
rm -rf "$CARRY_DIR"

# On failure restore only the two feeds the generator writes; any other feed
# is not ours to touch.
if ! "$PY" scripts/generate_farside_feeds.py; then
    git checkout -- public/feeds/farside-daily.xml public/feeds/farside-new.xml 2>/dev/null
    stop_slot generate-failed generate "$COUNT"
fi

# Name the slot that found the dose and the last one that missed it, so the
# commit itself records the publish window.
LAST_MISS="$("$PY" "$HELPER" last-miss --date "$SLOT_DATE")"
BODY="Found by the $(date +%H:%M) slot."
[ -n "$LAST_MISS" ] && BODY="$BODY The last slot that missed it ran at $LAST_MISS."

git add -f "$DAILY" public/feeds/farside-daily.xml
if ! git commit -q -m "Far Side Daily Dose for $SLOT_DATE" -m "$BODY" -- "$DAILY" public/feeds/farside-daily.xml; then
    # No commit of ours exists, and the operator may have edited since the
    # safe-sync check, so no --hard reset: unstage our two paths and restore the
    # feeds the generator rewrote (safe-sync proved they were clean beforehand).
    git reset -q -- "$DAILY" public/feeds/farside-daily.xml 2>/dev/null
    git checkout -- public/feeds/farside-daily.xml public/feeds/farside-new.xml 2>/dev/null
    stop_slot commit-failed commit "$COUNT"
fi
OUR_COMMIT="$(git rev-parse HEAD)"
# The generator rewrites the New Stuff feed too; it is not ours to ship.
git checkout -- public/feeds/farside-new.xml 2>/dev/null

push_with_watchdog() {
    ( exec git push origin main ) &
    local PUSH_PID=$!
    ( sleep 60 && pkill -TERM -P $PUSH_PID 2>/dev/null; kill -TERM $PUSH_PID 2>/dev/null; sleep 2; pkill -KILL -P $PUSH_PID 2>/dev/null; kill -KILL $PUSH_PID 2>/dev/null ) &
    local TIMER_PID=$!
    if wait $PUSH_PID 2>/dev/null; then
        kill $TIMER_PID 2>/dev/null; wait $TIMER_PID 2>/dev/null
        return 0
    fi
    kill $TIMER_PID 2>/dev/null; wait $TIMER_PID 2>/dev/null
    return 1
}

# `git push` exiting 0 is not proof of publication; see local_pass2_update.sh.
verify_push_landed() {
    git fetch -q origin main 2>/dev/null || return 1
    git merge-base --is-ancestor HEAD origin/main 2>/dev/null
}

if push_with_watchdog && verify_push_landed; then
    echo "✅ Shipped $DAILY ($COUNT strips) as $(git rev-parse --short HEAD)"
    log_slot shipped "$COUNT"
    report_pipeline_failures ""
    echo "================================================================================"
    exit 0
fi

# Drop only our own commit; the next slot finds the dose missing from
# origin/main and retries from scratch. Generation, commit, the push watchdog
# and the verify fetch all ran after the safe-sync check, so the operator may
# have committed or edited since: undo only while HEAD is still our commit, and
# with --keep, which refuses to overwrite local modifications. Otherwise leave
# the checkout exactly as it is.
echo "❌ Push failed or did not land"
if [ -n "$OUR_COMMIT" ] && [ "$(git rev-parse HEAD 2>/dev/null)" = "$OUR_COMMIT" ] && git reset -q --keep origin/main; then
    echo "↩️  Dropped our unpushed commit $(printf '%s' "$OUR_COMMIT" | cut -c1-7)"
else
    echo "⚠️  Checkout left as-is: HEAD moved or local changes block the undo; unpushed commit ${OUR_COMMIT:-unknown} may remain"
fi
stop_slot push-failed push "$COUNT"
