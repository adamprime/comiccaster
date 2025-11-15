#!/bin/bash
# Comics Kingdom Authentication Setup Script
# Run this to authenticate and generate cookies

echo "=========================================="
echo "Comics Kingdom Authentication Setup"
echo "=========================================="
echo ""

# Set environment variables
# REPLACE THESE WITH YOUR ACTUAL CREDENTIALS
export COMICSKINGDOM_USERNAME="your-email@example.com"
export COMICSKINGDOM_PASSWORD="your-password-here"
export COMICSKINGDOM_COOKIE_FILE="data/comicskingdom_cookies.pkl"

echo "✅ Environment variables set"
echo ""

# Run the re-authentication script
echo "🚀 Running authentication script..."
echo "This will open a browser window."
echo "Please solve the reCAPTCHA and click 'Log in' when prompted."
echo ""

venv/bin/python3 scripts/reauth_comicskingdom.py

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "If authentication succeeded, run:"
echo "  base64 -i data/comicskingdom_cookies.pkl | pbcopy"
echo ""
echo "Then paste into GitHub Secret: COMICSKINGDOM_COOKIES"
echo ""
