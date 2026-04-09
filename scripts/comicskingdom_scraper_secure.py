#!/usr/bin/env python3
"""
Secure authenticated scraper for Comics Kingdom.
Uses cookie persistence to avoid daily reCAPTCHA solving.
"""

import sys
import os
import json
import re
import argparse
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time


def get_required_env_var(name):
    """Get required environment variable or exit with error."""
    value = os.environ.get(name)
    if not value:
        print(f"❌ Error: Required environment variable {name} is not set")
        sys.exit(1)
    return value


def get_optional_env_var(name, default):
    """Get optional environment variable with default."""
    return os.environ.get(name, default)


def load_config_from_env():
    """Load configuration from environment variables."""
    config = {
        'credentials': {
            'username': get_required_env_var('COMICSKINGDOM_USERNAME'),
            'password': get_required_env_var('COMICSKINGDOM_PASSWORD'),
        },
        'cookie_file': Path(get_optional_env_var('COMICSKINGDOM_COOKIE_FILE', 'data/comicskingdom_cookies.pkl'))
    }
    
    print(f"✅ Loaded configuration from environment")
    print(f"   Cookie file: {config['cookie_file']}")
    
    return config


def setup_driver(show_browser=False):
    """Setup Chrome driver - simplified to match GoComics scraper."""
    options = Options()
    if not show_browser:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    # Anti-bot detection
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    
    # Set page load strategy and timeouts
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
        
        # Navigate to site first (required before adding cookies)
        print("🌐 Navigating to Comics Kingdom to load cookies...")
        try:
            driver.get("https://comicskingdom.com")
            time.sleep(2)
        except Exception as nav_error:
            print(f"⚠️  Navigation warning: {nav_error}")
            # Continue anyway - cookies might still work
        
        # Add all cookies
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"⚠️  Could not add cookie: {e}")
        
        print(f"✅ Loaded cookies from {cookie_file}")
        return True
    except Exception as e:
        print(f"❌ Error loading cookies: {e}")
        return False


def is_authenticated(driver):
    """Check if the current session is authenticated."""
    try:
        driver.get("https://comicskingdom.com/favorites")
        time.sleep(3)
        
        # If we're redirected to login page, we're not authenticated
        if 'login' in driver.current_url:
            return False
        
        # Check if we can see the favorites page content
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        if soup.find('h1') and 'favorites' in soup.find('h1').text.lower():
            return True
        
        return True  # Assume authenticated if not redirected to login
    except Exception as e:
        print(f"⚠️  Error checking authentication: {e}")
        return False


def login_with_manual_recaptcha(driver, username, password):
    """Login to Comics Kingdom with manual reCAPTCHA solving."""
    print("\n" + "="*80)
    print("COMICS KINGDOM LOGIN")
    print("="*80)
    print("Navigating to login page...")
    
    driver.get("https://comicskingdom.com/login")
    time.sleep(5)
    
    try:
        # Find and fill username field
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
        
        # Find password field
        password_field = driver.find_element(By.NAME, "password")
        
        # Fill credentials using JavaScript to avoid click interception
        print("Filling in credentials...")
        driver.execute_script(f"arguments[0].value = '{username}';", username_field)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", username_field)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", username_field)
        
        driver.execute_script(f"arguments[0].value = '{password}';", password_field)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", password_field)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", password_field)
        
        print("✅ Credentials filled")
        
        # Wait for manual reCAPTCHA solving
        print("\n" + "="*80)
        print("⏸️  PLEASE SOLVE THE reCAPTCHA AND CLICK LOGIN")
        print("="*80)
        print("Instructions:")
        print("  1. Check the reCAPTCHA box in the browser window")
        print("  2. Complete any image challenges if prompted")
        print("  3. Click the 'Log in' button")
        print("  4. Wait for the page to redirect")
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


def _click_load_more(driver, max_clicks=20):
    """Click 'Load more comics' button until all comics are loaded."""
    from selenium.webdriver.common.by import By

    clicks = 0
    for i in range(max_clicks):
        try:
            # Scroll to bottom first so the button is in viewport
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Try multiple selectors - the button has id="after-reader"
            btn = None
            for selector in [
                "#after-reader",
                ".ck-loadmore-button",
                ".ck-panel-reader__load-more-button",
                "button[aria-label='Load more comics']",
            ]:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        btn = el
                        break
                if btn:
                    break

            if not btn:
                # Also try by text content as last resort
                elements = driver.find_elements(
                    By.XPATH, "//button[contains(text(), 'Load more')]"
                )
                for el in elements:
                    if el.is_displayed():
                        btn = el
                        break

            if not btn:
                break

            # Scroll the button into view and click
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", btn)
            clicks += 1
            time.sleep(3)

        except Exception as e:
            print(f"  ⚠️  Load more click error: {e}")
            break

    print(f"  Clicked 'Load more' {clicks} time(s)")


def _decode_nextjs_image_url(src):
    """Extract the real image URL from a Next.js /_next/image proxy URL."""
    if '/_next/image' in src or 'url=' in src:
        match = re.search(r'url=([^&]+)', src)
        if match:
            import urllib.parse
            decoded = urllib.parse.unquote(match.group(1))
            if decoded.startswith('/'):
                decoded = 'https://comicskingdom.com' + decoded
            return decoded
    return src


def _save_diagnostic_snapshot(driver, output_dir, label):
    """Save a screenshot and HTML snapshot for debugging extraction failures."""
    diag_dir = Path(output_dir) / 'ck_diagnostics'
    diag_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    prefix = f"{timestamp}_{label}"

    try:
        driver.save_screenshot(str(diag_dir / f"{prefix}.png"))
        with open(diag_dir / f"{prefix}.html", 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"  Diagnostic snapshot saved to {diag_dir}/{prefix}.*")
    except Exception as e:
        print(f"  ⚠️  Could not save diagnostic snapshot: {e}")


def extract_comics_from_favorites(driver, date_str):
    """Extract all comics from the favorites page."""
    print(f"\n{'='*80}")
    print(f"Extracting comics from favorites page for {date_str}")
    print("="*80)

    driver.get("https://comicskingdom.com/favorites")
    time.sleep(5)

    # Try to dismiss any popups/interstitials
    try:
        from selenium.webdriver.common.by import By
        for selector in [
            "button[class*='close']", "[aria-label*='close']",
            "[aria-label*='Close']", "button[class*='dismiss']",
        ]:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                if el.is_displayed():
                    el.click()
                    time.sleep(1)
    except Exception:
        pass

    # Click "Load more comics" to load full favorites list
    print("Loading all comics...")
    _click_load_more(driver)

    # Force all lazy images to load by removing loading="lazy" and triggering loads
    print("Forcing lazy image load...")
    driver.execute_script("""
        document.querySelectorAll('img[loading="lazy"]').forEach(img => {
            img.loading = 'eager';
            if (!img.complete) {
                // Re-trigger load by resetting src
                const src = img.src;
                img.src = '';
                img.src = src;
            }
        });
    """)

    # Scroll through the page to ensure all images enter viewport at least briefly
    page_height = driver.execute_script("return document.body.scrollHeight")
    viewport = driver.execute_script("return window.innerHeight")
    position = 0
    while position < page_height:
        position += viewport
        driver.execute_script(f"window.scrollTo(0, {position});")
        time.sleep(0.5)
        page_height = driver.execute_script("return document.body.scrollHeight")
    driver.execute_script("window.scrollTo(0, 0);")

    # Wait for images to finish loading
    print("Waiting for images to load...")
    for attempt in range(10):
        loaded = driver.execute_script("""
            const imgs = document.querySelectorAll('[data-comic-item] img');
            return [imgs.length, [...imgs].filter(i => i.complete && i.naturalHeight > 0).length];
        """)
        total_imgs, complete_imgs = loaded
        if complete_imgs >= total_imgs and total_imgs > 0:
            break
        time.sleep(2)
    print(f"  {complete_imgs}/{total_imgs} images loaded")

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Primary extraction: use data-comic-item attributes (new CK DOM, 2026+)
    comic_items = soup.find_all(attrs={'data-comic-item': 'true'})
    print(f"Found {len(comic_items)} comic reader items")

    comics = []
    if comic_items:
        comics = _extract_via_data_attributes(comic_items, date_str)
    else:
        # Fallback: legacy extraction via img domain filtering
        print("  Falling back to legacy image-based extraction...")
        comics = _extract_via_image_scan(soup, date_str)

    if not comics:
        print("⚠️  Zero comics extracted — saving diagnostic snapshot")
        _save_diagnostic_snapshot(driver, 'data', 'zero_extraction')
        print(f"  Page URL: {driver.current_url}")
        print(f"  Page title: {driver.title}")
        print(f"  Total <img> tags: {len(soup.find_all('img'))}")

    print(f"✅ Extracted {len(comics)} comics from favorites page")

    if comics:
        print("\nSample comics:")
        for comic in comics[:5]:
            print(f"  - {comic['name']} ({comic['slug']})")

    return comics


def _extract_via_data_attributes(comic_items, date_str):
    """Extract comics using data-comic-item elements and their data-* attributes."""
    unique_comics = {}

    for item in comic_items:
        data_link = item.get('data-link', '')
        feature_name = item.get('data-feature-name', '')
        author = item.get('data-comic-author', '')
        published_date = item.get('data-published-date', date_str)

        if not data_link:
            continue

        # Extract slug from data-link (e.g. https://wp.comicskingdom.com/rosebuds/2026-04-09)
        # Vintage comics use a path like vintage/bringing-up-father/2026-04-09;
        # the catalog slug is the sub-slug (bringing-up-father), not the prefix.
        try:
            link_path = urlparse(data_link).path.strip('/')
            parts = link_path.split('/')
            # Strip date segments and the "vintage" URL grouping prefix
            slug_parts = [p for p in parts
                          if not re.match(r'^\d{4}-\d{2}-\d{2}$', p)
                          and p != 'vintage']
            comic_slug = '-'.join(slug_parts) if slug_parts else ''
        except Exception:
            continue

        if not comic_slug or comic_slug in unique_comics:
            continue

        # Collect all comic strip images inside this item
        image_urls = []
        for img in item.find_all('img'):
            src = img.get('src', '')
            if not src or 'placeholder' in src:
                continue
            actual_url = _decode_nextjs_image_url(src)
            # Only include actual comic images from the uploads directory
            if 'comicskingdom-redesign-uploads-production' in actual_url:
                image_urls.append(actual_url)

        comic_name = feature_name or comic_slug.replace('-', ' ').title()
        comic_url = f"https://comicskingdom.com/{comic_slug}/{published_date}"

        entry = {
            'name': comic_name,
            'slug': comic_slug,
            'date': published_date,
            'url': comic_url,
            'source': 'comicskingdom',
        }

        if len(image_urls) == 1:
            entry['image_url'] = image_urls[0]
        elif len(image_urls) > 1:
            entry['image_urls'] = image_urls
        else:
            # Comic item exists but images haven't loaded; include it anyway
            # so downstream feed generation can try the direct URL
            entry['image_url'] = ''

        unique_comics[comic_slug] = entry

    return [c for c in unique_comics.values() if c.get('image_url') or c.get('image_urls')]


def _extract_via_image_scan(soup, date_str):
    """Legacy fallback: extract comics by scanning all img tags for CK domains."""
    comics = []
    images = soup.find_all('img')
    print(f"  Found {len(images)} images total")

    for img in images:
        src = img.get('src', '')
        if not src:
            continue

        # Decode Next.js proxy URLs first
        actual_url = _decode_nextjs_image_url(src)

        try:
            parsed_src = urlparse(actual_url)
        except Exception:
            continue

        if ((parsed_src.netloc == 'wp.comicskingdom.com' or
             parsed_src.netloc.endswith('.comicskingdom.com')) and
            'placeholder' not in actual_url and
            'comicskingdom-redesign-uploads-production' in actual_url):

            parent = img.parent
            comic_link = None
            for _ in range(5):
                if parent:
                    link = parent.find('a', href=True)
                    if link and link['href'].startswith('/'):
                        comic_link = link['href']
                        break
                    parent = parent.parent

            if comic_link:
                parts = comic_link.strip('/').split('/')
                if len(parts) >= 1:
                    comic_slug = parts[0]
                    comic_name = comic_slug.replace('-', ' ').title()

                    comics.append({
                        'name': comic_name,
                        'slug': comic_slug,
                        'image_url': actual_url,
                        'date': date_str,
                        'url': f"https://comicskingdom.com{comic_link}",
                        'source': 'comicskingdom'
                    })

    # Deduplicate by slug, grouping multiple images
    unique_comics = {}
    for comic in comics:
        slug = comic['slug']
        if slug in unique_comics:
            if 'image_urls' not in unique_comics[slug]:
                unique_comics[slug]['image_urls'] = [unique_comics[slug].pop('image_url')]
            unique_comics[slug]['image_urls'].append(comic['image_url'])
        else:
            unique_comics[slug] = comic

    return list(unique_comics.values())


def authenticate_with_cookie_persistence(driver, config):
    """Authenticate using saved cookies or manual login."""
    cookie_file = config['cookie_file']
    
    # Check if running in CI environment
    is_ci = os.getenv('CI') == 'true' or os.getenv('GITHUB_ACTIONS') == 'true'
    
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
        if is_ci:
            # In CI, skip verification to avoid timeout issues
            print("✅ Running in CI - trusting saved cookies without verification")
            return True
        
        # Check if cookies are still valid (local only)
        print("🔍 Checking if cookies are still valid...")
        
        if is_authenticated(driver):
            print("✅ Successfully authenticated with saved cookies!")
            return True
        else:
            print("⚠️  Saved cookies are expired or invalid")
    
    # Need to login manually
    # Manual login only works locally, not in CI
    if is_ci:
        print("❌ Authentication failed in CI environment")
        print("Cookies may be expired. Run re-authentication locally and update GitHub Secret.")
        return False
    
    print("\n🔐 Manual login required")
    print("You'll need to solve the reCAPTCHA (this happens every ~60 days)")
    
    if login_with_manual_recaptcha(driver, 
                                   config['credentials']['username'],
                                   config['credentials']['password']):
        # Save cookies for future use
        save_cookies(driver, cookie_file)
        print("✅ Login successful and cookies saved!")
        return True
    else:
        print("❌ Login failed")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Secure authenticated scraper for Comics Kingdom with cookie persistence'
    )
    parser.add_argument('--date', help='Date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--output-dir', default='data', help='Output directory for JSON files')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window')
    parser.add_argument('--force-reauth', action='store_true', help='Force re-authentication (ignore saved cookies)')
    
    args = parser.parse_args()
    
    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load configuration from environment
    config = load_config_from_env()
    
    # Delete cookies if forced re-auth
    if args.force_reauth and config['cookie_file'].exists():
        config['cookie_file'].unlink()
        print("🗑️  Deleted saved cookies (force re-auth)")
    
    # Setup Chrome
    driver = setup_driver(show_browser=args.show_browser)
    
    try:
        # Authenticate (with cookie persistence)
        if not authenticate_with_cookie_persistence(driver, config):
            print("❌ Authentication failed")
            driver.quit()
            return 1
        
        # Extract comics from favorites page
        comics = extract_comics_from_favorites(driver, date_str)
        
        if not comics:
            print("⚠️  No comics extracted")
            driver.quit()
            return 1
        
        # Save results
        output_file = output_dir / f'comicskingdom_{date_str}.json'
        with open(output_file, 'w') as f:
            json.dump(comics, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"✅ SUCCESS! Extracted {len(comics)} comics for {date_str}")
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
