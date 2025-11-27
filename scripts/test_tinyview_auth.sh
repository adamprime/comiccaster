#!/bin/bash
# Quick test of TinyView authentication without interactive prompts

set -e

cd "$(dirname "$0")"

# Activate venv
if [ -d "venv/bin" ]; then
    source venv/bin/activate
    echo "✅ Activated venv"
fi

# Load environment
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep TINYVIEW | xargs)
    echo "✅ Loaded TinyView config from .env"
fi

# Check if email is set
if [ -z "$TINYVIEW_EMAIL" ]; then
    echo "❌ TINYVIEW_EMAIL not set in .env"
    echo "   Add: TINYVIEW_EMAIL=adam@tervort.org"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Email: $TINYVIEW_EMAIL"
echo "  Cookie file: ${TINYVIEW_COOKIE_FILE:-data/tinyview_cookies.pkl}"
echo ""

# Check if cookies already exist
if [ -f "${TINYVIEW_COOKIE_FILE:-data/tinyview_cookies.pkl}" ]; then
    echo "✅ Found existing cookies at ${TINYVIEW_COOKIE_FILE:-data/tinyview_cookies.pkl}"
    echo "   Testing if they still work..."
    
    python3 tinyview_scraper_secure.py --get-notifications --output-dir data
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "🎉 Authentication works! Your cookies are valid."
        exit 0
    else
        echo ""
        echo "⚠️  Cookies expired or invalid. Need to re-authenticate."
        echo ""
    fi
fi

echo "To authenticate for the first time, run:"
echo "  source venv/bin/activate"
echo "  python3 tinyview_scraper_secure.py --show-browser"
echo ""
echo "This will:"
echo "  1. Open a browser"
echo "  2. Let you complete magic link login"
echo "  3. Save cookies for future use"
echo ""
