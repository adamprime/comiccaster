#!/bin/bash

# TinyView Authentication Setup Script
# This script helps you authenticate with TinyView and save cookies for automated scraping

set -e

echo ""
echo "================================================================================"
echo "TinyView Authentication Setup"
echo "================================================================================"
echo ""
echo "This script will help you:"
echo "  1. Set up environment variables for TinyView authentication"
echo "  2. Authenticate with TinyView using magic link"
echo "  3. Save cookies for automated scraping"
echo ""

# This script lives in scripts/, but venv, .env, and data/ are all at the repo
# root. Resolve PROJECT_ROOT to the parent so paths match the daily run's cwd.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/venv/bin" ]; then
    echo "✅ Activating virtual environment..."
    source "$PROJECT_ROOT/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/.venv/bin" ]; then
    echo "✅ Activating virtual environment..."
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo "⚠️  No virtual environment found. Using system Python."
fi

# Check if .env file exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "✅ Found .env file"
    source "$PROJECT_ROOT/.env"
else
    echo "⚠️  No .env file found"
    echo "   Creating one from template..."
    
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo "✅ Created .env file from .env.example"
    else
        touch "$PROJECT_ROOT/.env"
        echo "✅ Created empty .env file"
    fi
fi

# Check if TINYVIEW_EMAIL is set
if [ -z "$TINYVIEW_EMAIL" ]; then
    echo ""
    echo "📧 TinyView Email"
    echo "   Enter your TinyView account email address"
    read -p "   Email: " TINYVIEW_EMAIL
    
    # Add to .env if not already there
    if ! grep -q "TINYVIEW_EMAIL" "$PROJECT_ROOT/.env"; then
        echo "TINYVIEW_EMAIL=$TINYVIEW_EMAIL" >> "$PROJECT_ROOT/.env"
        echo "✅ Saved TINYVIEW_EMAIL to .env"
    fi
fi

export TINYVIEW_EMAIL="$TINYVIEW_EMAIL"
echo ""
echo "Using email: $TINYVIEW_EMAIL"

# Set cookie file location
export TINYVIEW_COOKIE_FILE="$PROJECT_ROOT/data/tinyview_cookies.pkl"

echo ""
echo "================================================================================"
echo "Step 1: Authenticate with TinyView"
echo "================================================================================"
echo ""
echo "A browser window will open. Please:"
echo "  1. Click 'Send magic link' when prompted"
echo "  2. Check your email at: $TINYVIEW_EMAIL"
echo "  3. Click the magic link in the email"
echo "  4. Wait for the script to detect your login"
echo ""
read -p "Press Enter to continue..."

# Run the authentication
cd "$PROJECT_ROOT"
python3 scripts/tinyview_scraper_secure.py --show-browser

echo ""
echo "================================================================================"
echo "Step 2: Test Authentication"
echo "================================================================================"
echo ""
echo "Testing if we can use the saved cookies..."

# Test with notifications
python3 scripts/tinyview_scraper_secure.py --get-notifications

echo ""
echo "================================================================================"
echo "Step 3: Discover Comics"
echo "================================================================================"
echo ""
echo "Discovering all comics you follow on TinyView..."

python3 scripts/tinyview_scraper_secure.py --discover-comics

echo ""
echo "================================================================================"
echo "Setup Complete!"
echo "================================================================================"
echo ""
echo "Your TinyView authentication is set up and ready to use."
echo ""
echo "Files created:"
echo "  - data/tinyview_cookies.pkl (authentication cookies)"
echo "  - data/tinyview_notifications_*.json (recent updates)"
echo "  - data/tinyview_discovered_comics.json (all followed comics)"
echo ""
echo "Next steps:"
echo "  1. Compare discovered comics with public/tinyview_comics_list.json"
echo "  2. Add any missing comics to the list"
echo "  3. Update your automated scripts to use authentication"
echo ""
echo "To re-authenticate in the future, run:"
echo "  bash scripts/SETUP_TINYVIEW_AUTH.sh"
echo ""
