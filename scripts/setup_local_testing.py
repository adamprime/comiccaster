#!/usr/bin/env python3
"""
Local Testing Setup Script for TinyView Scraper

This script helps set up and validate the local environment for testing 
the TinyView scraper before pushing to GitHub Actions.
"""

import sys
import os
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_python_dependencies():
    """Check if required Python dependencies are installed."""
    logger.info("=== Checking Python Dependencies ===")
    
    required_packages = [
        ('selenium', 'selenium'),
        ('beautifulsoup4', 'bs4'), 
        ('requests', 'requests'),
        ('feedgen', 'feedgen')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name.replace('-', '_'))
            logger.info(f"✅ {package_name} is installed")
        except ImportError:
            logger.error(f"❌ {package_name} is missing")
            missing_packages.append(package_name)
    
    if missing_packages:
        logger.error(f"Please install missing packages: pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_firefox():
    """Check if Firefox is installed and accessible."""
    logger.info("\n=== Checking Firefox Installation ===")
    
    # Common Firefox locations on different systems
    firefox_paths = [
        'firefox',  # PATH
        '/usr/bin/firefox',  # Linux
        '/Applications/Firefox.app/Contents/MacOS/firefox',  # macOS
        '/usr/local/bin/firefox',  # Custom install
    ]
    
    firefox_found = False
    for path in firefox_paths:
        try:
            result = subprocess.run([path, '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info(f"✅ Firefox found at: {path}")
                logger.info(f"   Version: {result.stdout.strip()}")
                firefox_found = True
                break
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            continue
    
    if not firefox_found:
        logger.error("❌ Firefox not found. Please install Firefox:")
        logger.error("   macOS: brew install --cask firefox")
        logger.error("   Ubuntu: sudo apt-get install firefox")
        logger.error("   Or download from: https://www.mozilla.org/firefox/")
        return False
    
    return True

def check_geckodriver():
    """Check if geckodriver is installed and accessible."""
    logger.info("\n=== Checking Geckodriver ===")
    
    try:
        result = subprocess.run(['geckodriver', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"✅ Geckodriver found")
            logger.info(f"   Version: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass
    
    logger.error("❌ Geckodriver not found. Please install geckodriver:")
    logger.error("   macOS: brew install geckodriver")
    logger.error("   Ubuntu: See install_geckodriver_ubuntu.sh script")
    logger.error("   Or download from: https://github.com/mozilla/geckodriver/releases")
    return False

def create_geckodriver_install_script():
    """Create a script to install geckodriver on Ubuntu/Linux."""
    script_path = Path(__file__).parent / "install_geckodriver_ubuntu.sh"
    
    script_content = '''#!/bin/bash
# Install geckodriver on Ubuntu/Linux
set -e

GECKODRIVER_VERSION="v0.33.0"
echo "Installing geckodriver ${GECKODRIVER_VERSION}..."

# Download geckodriver
wget -q "https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"

# Extract and install
tar -xzf "geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"
sudo mv geckodriver /usr/local/bin/
sudo chmod +x /usr/local/bin/geckodriver

# Clean up
rm "geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"

echo "Geckodriver installed successfully!"
geckodriver --version
'''
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    logger.info(f"Created geckodriver install script: {script_path}")

def run_basic_selenium_test():
    """Run a basic Selenium test to verify everything works."""
    logger.info("\n=== Running Basic Selenium Test ===")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        
        # Set up Firefox options (similar to our scraper)
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        logger.info("Initializing Firefox WebDriver...")
        driver = webdriver.Firefox(options=options)
        
        logger.info("Testing basic navigation...")
        driver.get("https://httpbin.org/html")
        
        # Simple check that we can get content
        title = driver.title
        logger.info(f"Page title: {title}")
        
        driver.quit()
        logger.info("✅ Selenium test passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Selenium test failed: {e}")
        return False

def main():
    """Run all setup checks."""
    logger.info("TinyView Scraper Local Testing Setup")
    logger.info("=" * 50)
    
    all_checks_passed = True
    
    # Check Python dependencies
    if not check_python_dependencies():
        all_checks_passed = False
    
    # Check Firefox
    if not check_firefox():
        all_checks_passed = False
    
    # Check geckodriver
    if not check_geckodriver():
        all_checks_passed = False
        # Create install script for convenience
        create_geckodriver_install_script()
    
    if not all_checks_passed:
        logger.error("\n❌ Some dependencies are missing. Please install them first.")
        return False
    
    # Run Selenium test
    if not run_basic_selenium_test():
        logger.error("\n❌ Selenium test failed. Please check your setup.")
        return False
    
    logger.info("\n🎉 All checks passed! You can now test the TinyView scraper locally.")
    logger.info("Next steps:")
    logger.info("  1. Run: python scripts/test_tinyview_locally.py")
    logger.info("  2. Or run: python scripts/test_tinyview_fix.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)