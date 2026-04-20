#!/usr/bin/env python3
"""
Comics Kingdom scraper - visits individual comic pages.
More reliable than trying to parse the favorites page.
"""

import sys
import os
import json
import re
import argparse
import pickle
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


# Unit 1 instrumentation (2026-04-18). Timestamped log lines at every Chrome
# interaction boundary so we can see which call is hanging when the renderer
# timeout fires. Remove after Unit 3 lands.
# See docs/plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md
_SCRAPE_CALL_COUNT = 0


def _log_timing(label):
    """Print a timestamped marker line. Instrumentation only; no behavior change."""
    now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{now}] {label}")


def get_required_env_var(name):
    """Get required environment variable or exit with error."""
    value = os.environ.get(name)
    if not value:
        print(f"❌ Error: Required environment variable {name} is not set")
        sys.exit(1)
    return value


def load_config_from_env(require_credentials=True):
    """Load configuration from environment variables.

    When require_credentials is False, COMICSKINGDOM_USERNAME and
    COMICSKINGDOM_PASSWORD may be unset (they land as None). Use
    require_credentials=False on the daily-scrape path under profile-based
    auth, where credentials are not needed. Use require_credentials=True
    (default) for the reauth flow, which does need them.
    """
    if require_credentials:
        username = get_required_env_var('COMICSKINGDOM_USERNAME')
        password = get_required_env_var('COMICSKINGDOM_PASSWORD')
    else:
        username = os.environ.get('COMICSKINGDOM_USERNAME')
        password = os.environ.get('COMICSKINGDOM_PASSWORD')

    config = {
        'credentials': {
            'username': username,
            'password': password,
        },
        'cookie_file': Path(get_optional_env_var('COMICSKINGDOM_COOKIE_FILE', 'data/comicskingdom_cookies.pkl'))
    }

    print(f"✅ Loaded configuration from environment")
    print(f"   Cookie file: {config['cookie_file']}")

    return config


def get_optional_env_var(name, default):
    """Get optional environment variable with default."""
    return os.environ.get(name, default)


def setup_driver(show_browser=False, use_profile=True):
    """Setup Chrome driver.

    Defaults to use_profile=True (Shape A). Chrome launches with --user-data-dir
    pointing at ~/.comicskingdom_chrome_profile. The profile carries session
    cookies so the first request to CK arrives authenticated -- this bypasses
    the WAF slow-walk that was the root cause of the chronic renderer timeout
    (see docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md).

    Pass use_profile=False to fall back to the legacy pickled-cookie flow
    (kept for rollback; expected to be removed once Shape A proves out).
    """
    options = Options()
    if not show_browser:
        options.add_argument('--headless=new')

    if use_profile:
        profile_dir = Path.home() / '.comicskingdom_chrome_profile'
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_dir.chmod(0o700)
        options.add_argument(f'--user-data-dir={profile_dir}')
        print(f"🔧 Using Chrome profile: {profile_dir}")

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    # Anti-bot detection
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    _log_timing("setup_driver: webdriver.Chrome() START")
    driver = webdriver.Chrome(options=options)
    _log_timing("setup_driver: webdriver.Chrome() END")

    # Set timeouts
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    driver.implicitly_wait(10)
    
    # Remove webdriver property
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def save_cookies(driver, cookie_file):
    """Save authentication cookies to file."""
    cookies = driver.get_cookies()
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookie_file, 'wb') as f:
        pickle.dump(cookies, f)
    print(f"✅ Cookies saved to {cookie_file}")


def load_cookies(driver, cookie_file):
    """Load saved cookies and add them to the driver."""
    if not cookie_file.exists():
        return False
    
    try:
        with open(cookie_file, 'rb') as f:
            cookies = pickle.load(f)
        
        # Navigate to site first
        _log_timing("load_cookies: driver.get(comicskingdom.com) START")
        driver.get("https://comicskingdom.com")
        _log_timing("load_cookies: driver.get(comicskingdom.com) END")
        time.sleep(2)

        # Add all cookies
        _log_timing("load_cookies: add_cookie loop START")
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                pass
        _log_timing("load_cookies: add_cookie loop END")

        print(f"✅ Loaded cookies from {cookie_file}")
        return True
    except Exception as e:
        print(f"❌ Error loading cookies: {e}")
        return False


def is_authenticated(driver):
    """Check if the current session is authenticated."""
    try:
        _log_timing("is_authenticated: driver.get(/favorites) START")
        driver.get("https://comicskingdom.com/favorites")
        _log_timing("is_authenticated: driver.get(/favorites) END")
        time.sleep(2)

        if 'login' in driver.current_url:
            return False

        return True
    except Exception as e:
        return False


def authenticate_with_cookies(driver, config, use_profile=False):
    """Authenticate either via a persistent Chrome profile or pickled cookies.

    When use_profile is True, Chrome is expected to have launched with
    --user-data-dir pointing at ~/.comicskingdom_chrome_profile. The session
    cookies are already in the browser, so we skip the pickled-cookie load
    entirely and just verify authentication. This is the Shape A path; see
    docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md.

    When use_profile is False, use the legacy pickled-cookie flow.
    """
    if use_profile:
        profile_dir = Path.home() / '.comicskingdom_chrome_profile'
        cookies_db = profile_dir / 'Default' / 'Cookies'

        if is_authenticated(driver):
            print("✅ Successfully authenticated with Chrome profile!")
            return True

        # Distinguish "profile never seeded" from "profile has a dead session".
        # Chrome creates Default/Cookies on the first authenticated navigation,
        # so its absence is a reliable signal that reauth has never run.
        if not cookies_db.exists():
            print(f"⚠️  Chrome profile at {profile_dir} has no stored session.")
            print("   Run scripts/reauth_comicskingdom.py to seed it.")
            return False

        print("❌ Authentication failed - please run reauth script")
        return False

    cookie_file = config['cookie_file']

    # Check cookie age
    if cookie_file.exists():
        cookie_age_days = (datetime.now() - datetime.fromtimestamp(
            cookie_file.stat().st_mtime
        )).days
        print(f"📅 Cookie file is {cookie_age_days} days old")

        if cookie_age_days > 60:
            print(f"⚠️  Cookies are old. Recommend re-authentication.")

    # Try to load existing cookies
    if load_cookies(driver, cookie_file):
        print("🔍 Checking if cookies are still valid...")

        if is_authenticated(driver):
            print("✅ Successfully authenticated with saved cookies!")
            return True
        else:
            print("⚠️  Saved cookies are expired or invalid")

    print("❌ Authentication failed - please run reauth script")
    return False


def login_with_manual_recaptcha(driver):
    """Wait for the operator to log in manually in a visible browser window.

    Comics Kingdom uses an invisible reCAPTCHA v3 and a bot check that rejects
    JS-injected credential fills, so the operator types credentials directly
    into the page. This function opens the login page, confirms the form is
    present, then polls for redirect away from /login.
    """
    print("\n" + "="*80)
    print("COMICS KINGDOM LOGIN")
    print("="*80)
    print("Navigating to login page...")

    driver.get("https://comicskingdom.com/login")
    time.sleep(5)

    try:
        # Confirm the login form is present before handing off to the operator
        username_field = None
        selectors = [
            (By.NAME, "username"),
            (By.ID, "username"),
            (By.CSS_SELECTOR, "input[name='username']"),
        ]

        for selector_type, selector_value in selectors:
            try:
                username_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                break
            except:
                continue

        if not username_field:
            print("❌ Could not find username field")
            return False

        print("\n" + "="*80)
        print("⏸️  PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW")
        print("="*80)
        print("Instructions:")
        print("  1. Click into the Username field and type (or paste) your username.")
        print("  2. Click into the Password field and type (or paste) your password.")
        print("  3. Click the 'Log in' button.")
        print("  4. If an image challenge appears, complete it.")
        print("  5. Wait for the page to redirect away from /login.")
        print("\nNote: CK uses an invisible reCAPTCHA — there is no checkbox to tick.")
        print("JS-injected credential fills are rejected by their bot check, which")
        print("is why you have to type or paste directly.")
        print("\n⏳ Waiting for you to complete login...")
        print("="*80 + "\n")

        # Wait for navigation away from login page
        for i in range(120):  # Wait up to 2 minutes
            time.sleep(1)
            current_url = driver.current_url

            if 'login' not in current_url:
                print(f"\n✅ Login successful! Redirected to: {current_url}")
                time.sleep(3)  # Give page time to fully load
                return True

            if (i+1) % 15 == 0:
                print(f"  ...still waiting ({i+1}/120 seconds)...")

        print("\n❌ Timeout waiting for login")
        return False

    except Exception as e:
        print(f"❌ Login failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_comics_catalog():
    """Load Comics Kingdom comics from catalog."""
    catalog_path = Path('public/comics_list.json')
    
    with open(catalog_path, 'r') as f:
        all_comics = json.load(f)
    
    # Filter for Comics Kingdom comics
    ck_comics = [c for c in all_comics if c.get('source') == 'comicskingdom']
    
    print(f"📚 Loaded {len(ck_comics)} Comics Kingdom comics from catalog")
    return ck_comics


def scrape_comic_page(driver, comic_slug, date_str, debug=False):
    """Scrape a single comic page."""
    global _SCRAPE_CALL_COUNT
    _SCRAPE_CALL_COUNT += 1
    url = f"https://comicskingdom.com/{comic_slug}/{date_str}"

    try:
        if _SCRAPE_CALL_COUNT <= 5:
            _log_timing(f"scrape_comic_page[{_SCRAPE_CALL_COUNT}]: driver.get({comic_slug}) START")
        driver.get(url)
        if _SCRAPE_CALL_COUNT <= 5:
            _log_timing(f"scrape_comic_page[{_SCRAPE_CALL_COUNT}]: driver.get({comic_slug}) END")
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find comic strip images - look in the main comic reader container
        # Comics Kingdom uses specific containers for today's comic:
        # - .comic-reader-item or .ck-multiple-panel-reader contains today's panels
        # - Parent containers may have archive/navigation images
        
        image_urls = []
        
        # Try to find the comic reader container first
        comic_container = soup.find('div', class_=lambda x: x and ('comic-reader-item' in x or 'ck-multiple-panel-reader' in x))
        
        if not comic_container:
            # Fallback: look for any container with class containing "comic" or "reader"
            comic_container = soup.find('div', class_=lambda x: x and any(keyword in x.lower() for keyword in ['comic', 'reader', 'strip']))
        
        if not comic_container:
            # Last resort: use entire page
            if debug:
                print(f"    ⚠️  Could not find comic container, using entire page")
            comic_container = soup
        
        # Find all images within the comic container
        images = comic_container.find_all('img')
        
        for img in images:
            src = img.get('src', '')
            
            # Skip if not a Comics Kingdom image
            if 'wp.comicskingdom.com' not in src:
                continue
            
            # Extract actual URL if Next.js optimized
            actual_url = src
            if 'url=' in src:
                match = re.search(r'url=([^&]+)', src)
                if match:
                    import urllib.parse
                    actual_url = urllib.parse.unquote(match.group(1))
            
            image_urls.append(actual_url)
        
        if debug and image_urls:
            print(f"    Found {len(image_urls)} image(s) in comic container")
        
        if not image_urls:
            if debug:
                print(f"    No images found with date {date_str}")
            return None
        
        if debug:
            print(f"    Found {len(image_urls)} images with today's date")
        
        # Get comic name from page title or slug
        comic_name = comic_slug.replace('-', ' ').title()
        title_tag = soup.find('title')
        if title_tag:
            # Extract name from title like "Blondie Comic Strip 2025-11-15 | Comics Kingdom"
            title_text = title_tag.text
            if '|' in title_text:
                comic_name = title_text.split('|')[0].strip().replace(' Comic Strip', '').replace(f' {date_str}', '')
        
        comic_data = {
            'name': comic_name,
            'slug': comic_slug,
            'date': date_str,
            'url': url,
            'source': 'comicskingdom'
        }
        
        if len(image_urls) == 1:
            comic_data['image_url'] = image_urls[0]
        else:
            comic_data['image_urls'] = image_urls
        
        return comic_data
        
    except Exception as e:
        print(f"  ⚠️  Error scraping {comic_slug}: {e}")
        return None


def scrape_all_comics(driver, comics, date_str):
    """Scrape all comics sequentially."""
    print(f"\n{'='*80}")
    print(f"Scraping {len(comics)} Comics Kingdom comics for {date_str}")
    print("="*80)
    
    results = []
    success_count = 0
    
    for i, comic in enumerate(comics, 1):
        slug = comic['slug']
        print(f"[{i}/{len(comics)}] Scraping {comic['name']} ({slug})...")
        
        comic_data = scrape_comic_page(driver, slug, date_str, debug=False)
        
        if comic_data:
            results.append(comic_data)
            success_count += 1
        
        # Small delay between requests
        time.sleep(0.5)
    
    print(f"\n✅ Successfully scraped {success_count}/{len(comics)} comics")
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Comics Kingdom scraper - visits individual comic pages'
    )
    parser.add_argument('--date', help='Date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--output-dir', default='data', help='Output directory for JSON files')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window')
    parser.add_argument(
        '--no-profile',
        action='store_false',
        dest='use_profile',
        default=True,
        help='Disable the persistent Chrome profile and fall back to the '
             'legacy pickled-cookie flow (for debugging / rollback only; '
             'default is profile-based auth).',
    )

    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load configuration. Credentials are only required when seeding the
    # profile (reauth). Daily scrape under --use-profile does not need them.
    config = load_config_from_env(require_credentials=not args.use_profile)

    # Load comics catalog
    comics = load_comics_catalog()

    # Setup Chrome
    driver = setup_driver(show_browser=args.show_browser, use_profile=args.use_profile)

    try:
        # Authenticate
        if not authenticate_with_cookies(driver, config, use_profile=args.use_profile):
            print("❌ Authentication failed")
            driver.quit()
            return 1
        
        # Scrape all comics
        results = scrape_all_comics(driver, comics, date_str)
        
        if not results:
            print("⚠️  No comics scraped")
            driver.quit()
            return 1
        
        # Save results
        output_file = output_dir / f'comicskingdom_{date_str}.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"✅ SUCCESS! Scraped {len(results)} comics for {date_str}")
        print(f"💾 Saved to {output_file}")
        print(f"{'='*80}\n")
        
        driver.quit()
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return 1


if __name__ == "__main__":
    sys.exit(main())
