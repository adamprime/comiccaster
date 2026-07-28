#!/usr/bin/env python3
"""
Re-authentication helper for Comics Kingdom.

Seeds the persistent Chrome profile at ~/.comicskingdom_chrome_profile by
opening a visible Chrome window, letting the operator type credentials and
log in, and then closing the window so Chrome persists the session into
the profile.

CK's token lasts **7 days**, and the operator reauths weekly -- so the margin
is hours, and a reauth that silently fails to mint a new token means a failed
run the next morning (2026-07-28). This script therefore reads the token expiry
before and after login and tells you whether it actually moved. Trust that
line, not the browser looking logged in.

Let this script close the browser. Closing the window by hand can leave Chrome's
new cookies unflushed, which produces exactly that silent failure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from scripts.comicskingdom_scraper_individual import (
    setup_driver,
    wait_for_manual_login,
)
from scripts.check_ck_session import describe_renewal, read_token_expiry


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

    # Recorded now so we can prove the login actually issued a new token.
    expiry_before = read_token_expiry(PROFILE_DIR)
    if expiry_before:
        print(f"\n📅 Current session expires: {expiry_before:%Y-%m-%d %H:%M UTC}")
    else:
        print("\n📅 No existing session token found (fresh profile).")

    print("\n🌐 Opening browser with persistent profile...")
    driver = setup_driver(show_browser=True, use_profile=True)

    try:
        if wait_for_manual_login(driver):
            print("\n" + "="*80)
            print("✅ SUCCESS! Re-authentication complete")
            print("="*80)
            print(f"\nProfile seeded at: {PROFILE_DIR}")
            print("No pickled cookies were written.")
            print("="*80 + "\n")

            # Quit first: Chrome writes cookies to disk on clean shutdown, so
            # reading before this would see the pre-login state.
            driver.quit()

            renewed, message = describe_renewal(
                expiry_before, read_token_expiry(PROFILE_DIR),
                datetime.now(timezone.utc),
            )
            print("="*80)
            print(f"{'✅' if renewed else '❌'} {message}")
            print("="*80 + "\n")
            return 0 if renewed else 1
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
