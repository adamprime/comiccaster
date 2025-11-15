#!/usr/bin/env python3
"""
Re-authentication helper for Comics Kingdom.
Run this script when cookies expire (every ~60 days).
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import comicskingdom_scraper_secure
sys.path.insert(0, str(Path(__file__).parent.parent))

from comicskingdom_scraper_secure import (
    setup_driver,
    load_config_from_env,
    authenticate_with_cookie_persistence
)


def main():
    """Re-authenticate with Comics Kingdom and save new cookies."""
    print("="*80)
    print("COMICS KINGDOM RE-AUTHENTICATION")
    print("="*80)
    print("\nThis script will:")
    print("  1. Delete your old cookies")
    print("  2. Open a browser window")
    print("  3. Wait for you to solve reCAPTCHA and login")
    print("  4. Save new cookies for ~60 days of automated use")
    print("\n" + "="*80 + "\n")
    
    input("Press ENTER to continue...")
    
    # Load configuration
    config = load_config_from_env()
    
    # Delete old cookies
    if config['cookie_file'].exists():
        config['cookie_file'].unlink()
        print(f"🗑️  Deleted old cookies from {config['cookie_file']}")
    
    # Setup driver (with visible browser)
    print("\n🌐 Opening browser...")
    driver = setup_driver(show_browser=True)
    
    try:
        # Authenticate (will force manual login)
        if authenticate_with_cookie_persistence(driver, config):
            print("\n" + "="*80)
            print("✅ SUCCESS! Re-authentication complete")
            print("="*80)
            print(f"\nNew cookies saved to: {config['cookie_file']}")
            print("These cookies will be valid for ~60 days")
            print("\nYou can now run the Comics Kingdom scraper normally.")
            print("="*80 + "\n")
            driver.quit()
            return 0
        else:
            print("\n❌ Re-authentication failed")
            driver.quit()
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        driver.quit()
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return 1


if __name__ == "__main__":
    sys.exit(main())
