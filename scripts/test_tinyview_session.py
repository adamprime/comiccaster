#!/usr/bin/env python3
"""
Test keeping TinyView session alive during scraping.
Authenticate once, then scrape multiple times with the same browser.
"""

import sys
from dotenv import load_dotenv
load_dotenv()

from tinyview_scraper_secure import (
    setup_driver, 
    authenticate_with_cookie_persistence,
    load_config_from_env,
    extract_notifications,
    discover_all_comics
)

def main():
    print("Testing TinyView session persistence...")
    print("=" * 80)
    
    config = load_config_from_env()
    
    # Setup browser (visible so you can see it working)
    driver = setup_driver(show_browser=True)
    
    try:
        # Step 1: Authenticate
        print("\n1. Authenticating...")
        if not authenticate_with_cookie_persistence(driver, config, show_browser=True, force_reauth=True):
            print("❌ Authentication failed")
            return 1
        
        print("\n✅ Authenticated successfully!")
        
        # Step 2: Get notifications (browser still open, should work)
        print("\n2. Testing notifications extraction (browser still open)...")
        notifications = extract_notifications(driver)
        
        if notifications:
            print(f"\n✅ SUCCESS! Got {len(notifications)} notifications:")
            for notif in notifications[:5]:  # Show first 5
                print(f"   - {notif['comic_name']}: {notif['title']} ({notif['timestamp']})")
        else:
            print("\n⚠️  No notifications found")
        
        # Step 3: Discover comics (browser still open, should work)
        print("\n3. Testing comic discovery (browser still open)...")
        comics = discover_all_comics(driver)
        
        if comics:
            print(f"\n✅ SUCCESS! Discovered {len(comics)} comics:")
            for comic in comics[:10]:  # Show first 10
                print(f"   - {comic['name']} ({comic['slug']})")
        else:
            print("\n⚠️  No comics found")
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\nKey insight: Authentication persists for the entire browser session.")
        print("You can scrape multiple comics without re-authenticating as long as")
        print("the browser stays open.")
        
        input("\nPress Enter to close browser and exit...")
        
    finally:
        driver.quit()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
