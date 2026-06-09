#!/bin/bash
# Safety net for the daily ComicCaster pipeline.
#
# The primary daily run is driven by ~/Library/LaunchAgents/com.comiccaster.master.plist
# (StartCalendarInterval 03:05). User-level LaunchAgents only fire while a user
# session exists, so a forced overnight macOS reboot can leave the host at the
# loginwindow past 03:05 and the daily run gets silently skipped (see incident
# 2026-05-26).
#
# This script is wired to a *separate* LaunchAgent with RunAtLoad=true so it
# runs once each time the user logs in (typically once a day, at boot). If
# today's GoComics data file already exists, it exits cleanly -- no double-run.
# If not, it execs the production entrypoint to catch up on the missed slot.
#
# We use data/comics_<DATE>.json as the canary because GoComics is the first
# source scraped each day; its presence is a reliable indicator that the
# primary 03:05 run completed at least Phase 1.

set -eu

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY="$(date +%Y-%m-%d)"
CANARY="$REPO_DIR/data/comics_$TODAY.json"

if [ -f "$CANARY" ]; then
    echo "[$(date -Iseconds)] Catch-up: $CANARY present, today's run already happened. Skipping."
    exit 0
fi

echo "[$(date -Iseconds)] Catch-up: $CANARY missing. Running master update."
exec "$REPO_DIR/scripts/mini_master_update.sh"
