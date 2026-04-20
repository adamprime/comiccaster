#!/usr/bin/env python3
"""
Re-authentication helper for Comics Kingdom.

Seeds the persistent Chrome profile at ~/.comicskingdom_chrome_profile by
opening a visible Chrome window, letting the operator type credentials and
log in, and then closing the window so Chrome persists the session into
the profile. Run this when the session expires (typically every ~60 days,
or when the daily scrape reports "profile has no stored session").
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.comicskingdom_scraper_individual import (
    setup_driver,
    login_with_manual_recaptcha,
)


PROFILE_DIR = Path.home() / '.comicskingdom_chrome_profile'


def main():
    """Re-authenticate with Comics Kingdom by seeding the Chrome profile."""
    print("="*80)
    print("COMICS KINGDOM RE-AUTHENTICATION")
    print("="*80)
    print("\nThis script will:")
    print("  1. Open a Chrome window using the persistent profile at")
    print(f"     {PROFILE_DIR}")
    print("  2. Navigate to the CK login page and wait for you to type")
    print("     credentials and click Log in")
    print("  3. Close cleanly so Chrome persists the session")
    print("\nCredentials are NOT read from .env — you type them directly into")
    print("the browser because CK's bot check rejects JS-injected fills.")
    print("\nAfter this completes, the daily scrape can authenticate without")
    print("pickled cookies and without hitting the WAF slow-walk on startup.")
    print("\n" + "="*80 + "\n")

    input("Press ENTER to continue...")

    print("\n🌐 Opening browser with persistent profile...")
    driver = setup_driver(show_browser=True, use_profile=True)

    try:
        if login_with_manual_recaptcha(driver):
            print("\n" + "="*80)
            print("✅ SUCCESS! Re-authentication complete")
            print("="*80)
            print(f"\nProfile seeded at: {PROFILE_DIR}")
            print("The daily scrape will pick up this session on its next run.")
            print("No pickled cookies were written.")
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
