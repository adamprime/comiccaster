#!/bin/bash

# Install Local TinyView Automation
# This script sets up a launchd agent to run TinyView scraping at 12:35 AM daily

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Installing TinyView Local Automation${NC}\n"

# Get script directory and project path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Project directory: $PROJECT_DIR"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Create the plist file from template
PLIST_TEMPLATE="$SCRIPT_DIR/com.comiccaster.tinyview.plist"
PLIST_FILE="$HOME/Library/LaunchAgents/com.comiccaster.tinyview.plist"

if [ ! -f "$PLIST_TEMPLATE" ]; then
    echo -e "${RED}Error: Template file not found: $PLIST_TEMPLATE${NC}"
    exit 1
fi

# Replace placeholder with actual project path
sed "s|REPLACE_WITH_PROJECT_PATH|$PROJECT_DIR|g" "$PLIST_TEMPLATE" > "$PLIST_FILE"

echo -e "${GREEN}✓${NC} Created plist file: $PLIST_FILE"

# Load the agent
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo -e "${GREEN}✓${NC} Loaded launchd agent"

# Check status
if launchctl list | grep -q "com.comiccaster.tinyview"; then
    echo -e "\n${GREEN}✓ TinyView automation installed successfully!${NC}\n"
    echo "The scraper will run daily at 12:35 AM"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    tail -f $PROJECT_DIR/logs/tinyview_local.log"
    echo "  Check status: launchctl list | grep tinyview"
    echo "  Unload:       launchctl unload $PLIST_FILE"
    echo "  Test now:     bash $SCRIPT_DIR/local_tinyview_update.sh"
else
    echo -e "${RED}✗ Failed to load launchd agent${NC}"
    exit 1
fi
