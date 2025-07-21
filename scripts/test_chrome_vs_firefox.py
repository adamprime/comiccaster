#!/usr/bin/env python3
"""
Test which WebDriver works better - Chrome or Firefox
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comiccaster.tinyview_scraper import TinyviewScraper

def test_webdriver_choice():
    """Test which WebDriver gets used."""
    print("Testing WebDriver Selection")
    print("=" * 30)
    
    scraper = TinyviewScraper()
    
    try:
        scraper.setup_driver()
        
        # Check which driver is actually running
        driver_name = scraper.driver.capabilities.get('browserName', 'unknown')
        driver_version = scraper.driver.capabilities.get('browserVersion', 'unknown')
        
        print(f"✅ WebDriver initialized successfully!")
        print(f"Browser: {driver_name}")
        print(f"Version: {driver_version}")
        
        # Test a simple navigation
        scraper.driver.get("https://httpbin.org/html")
        title = scraper.driver.title
        print(f"Test navigation successful: {title}")
        
        return True
        
    except Exception as e:
        print(f"❌ WebDriver failed: {e}")
        return False
    finally:
        scraper.close_driver()

if __name__ == "__main__":
    success = test_webdriver_choice()
    if success:
        print("\n🎉 WebDriver test passed!")
    else:
        print("\n❌ WebDriver test failed!")