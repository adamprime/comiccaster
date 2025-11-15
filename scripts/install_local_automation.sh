#!/bin/bash
# Install macOS launchd agent for Comics Kingdom daily automation

set -e

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
PLIST_FILE="$REPO_DIR/scripts/com.comiccaster.comicskingdom.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LAUNCHD_PLIST="$LAUNCHD_DIR/com.comiccaster.comicskingdom.plist"

echo "================================================================================"
echo "Installing Comics Kingdom Local Automation"
echo "================================================================================"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCHD_DIR"

# Copy plist file to LaunchAgents
echo "Copying launchd plist to $LAUNCHD_PLIST..."
cp "$PLIST_FILE" "$LAUNCHD_PLIST"

# Update paths in plist to use actual home directory
sed -i '' "s|/Users/adam|$HOME|g" "$LAUNCHD_PLIST"

echo "✅ Plist file installed"

# Unload existing agent if running
if launchctl list | grep -q "com.comiccaster.comicskingdom"; then
    echo "Unloading existing agent..."
    launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
fi

# Load the agent
echo "Loading launchd agent..."
launchctl load "$LAUNCHD_PLIST"

if [ $? -eq 0 ]; then
    echo "✅ Successfully installed Comics Kingdom automation"
    echo ""
    echo "Configuration:"
    echo "  - Runs daily at 12:30 AM local time"
    echo "  - Before GitHub Actions run at 1 AM PST / 2 AM PDT"
    echo "  - Logs: $REPO_DIR/logs/"
    echo ""
    echo "To manually trigger:"
    echo "  $REPO_DIR/scripts/local_comicskingdom_update.sh"
    echo ""
    echo "To check status:"
    echo "  launchctl list | grep comicskingdom"
    echo ""
    echo "To view logs:"
    echo "  tail -f $REPO_DIR/logs/comicskingdom_local.log"
    echo ""
    echo "To uninstall:"
    echo "  launchctl unload $LAUNCHD_PLIST"
    echo "  rm $LAUNCHD_PLIST"
else
    echo "❌ Failed to load launchd agent"
    exit 1
fi

echo "================================================================================"
