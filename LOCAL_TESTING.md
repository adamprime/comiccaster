# Local Testing Guide for TinyView Scraper

This guide helps you test the TinyView scraper locally before using GitHub Actions minutes.

## Quick Start

1. **Check if you have the dependencies:**
   ```bash
   python3 scripts/setup_local_testing.py
   ```

2. **If everything is installed, run the test:**
   ```bash
   python3 scripts/test_tinyview_fix.py
   ```

## Installation Steps

### macOS

1. **Install Firefox:**
   ```bash
   brew install --cask firefox
   ```

2. **Install geckodriver:**
   ```bash
   brew install geckodriver
   ```

3. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

### Ubuntu/Linux

1. **Install Firefox:**
   ```bash
   sudo apt-get update
   sudo apt-get install firefox
   ```

2. **Install geckodriver:** 
   ```bash
   # Run the generated script
   chmod +x scripts/install_geckodriver_ubuntu.sh
   ./scripts/install_geckodriver_ubuntu.sh
   ```

3. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

### Windows

1. **Install Firefox:** Download from https://www.mozilla.org/firefox/
2. **Install geckodriver:** Download from https://github.com/mozilla/geckodriver/releases
   - Extract and add to PATH
3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## What the Tests Do

The local test suite will:

1. ✅ **Setup Check** - Verify Firefox WebDriver can initialize
2. ✅ **Comic Scraping** - Test scraping multiple comics (lunarbaboon, nick-anderson, adhdinos)
3. ✅ **Feed Generation** - Generate a test RSS feed in `test_feeds/`

## Understanding Results

- ✅ **Success**: The test worked as expected
- ⚠️ **Warning**: Expected behavior (e.g., no comic published on that date)
- ❌ **Error**: Something is broken and needs fixing

## Common Issues

### "geckodriver not found"
- **macOS**: `brew install geckodriver`
- **Linux**: Run `scripts/install_geckodriver_ubuntu.sh`
- **Windows**: Download and add to PATH

### "Firefox not found"
- Make sure Firefox is installed and in your PATH
- On macOS, the script checks `/Applications/Firefox.app/Contents/MacOS/firefox`

### "Module not found: selenium"
- Run: `pip3 install -r requirements.txt`
- Make sure you're in the project directory

## Interpreting Test Results

If local tests pass but GitHub Actions fails, it's likely a CI-specific issue (different versions, paths, etc.).

If local tests fail, we need to fix the scraper logic before trying GitHub Actions.

## Test Output Files

- `test_feeds/lunarbaboon.xml` - Generated RSS feed for inspection
- Check this file to see if comics are being scraped correctly

## Debugging

For more detailed output, edit the test script to change logging level:
```python
logging.basicConfig(level=logging.DEBUG, ...)
```