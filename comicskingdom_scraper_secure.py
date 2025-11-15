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
    """Setup Chrome driver with timeouts for CI stability."""
    options = Options()
    
    # Headless mode
    if not show_browser:
        options.add_argument('--headless=new')
    
    # Critical options for Linux servers
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-setuid-sandbox')
    
    # User agent for Linux
    options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    print("🌐 Initializing Chrome WebDriver...")
    driver = webdriver.Chrome(options=options)
    
    # Set aggressive timeouts for CI environments
    driver.set_page_load_timeout(60)  # Max 60 seconds to load a page
    driver.set_script_timeout(30)      # Max 30 seconds for scripts
    driver.implicitly_wait(10)         # Max 10 seconds for elements
    
    print("✅ Chrome WebDriver initialized")
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
        driver.get("https://comicskingdom.com")
        time.sleep(1)
        
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


def extract_comics_from_favorites(driver, date_str):
    """Extract all comics from the favorites page."""
    print(f"\n{'='*80}")
    print(f"Extracting comics from favorites page for {date_str}")
    print("="*80)
    
    driver.get("https://comicskingdom.com/favorites")
    time.sleep(5)
    
    # Scroll to load lazy images
    print("Scrolling to load all images...")
    for i in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Find all comic strip images
    comics = []
    
    # Look for images with Comics Kingdom URLs
    images = soup.find_all('img')
    print(f"Found {len(images)} images total")
    
    for img in images:
        src = img.get('src', '')
        alt = img.get('alt', '')
        
        # Filter for actual comic strip images
        if 'wp.comicskingdom.com' in src and 'placeholder' not in src:
            # Try to extract comic info from nearby links or alt text
            parent = img.parent
            
            # Look for link to comic page
            comic_link = None
            for _ in range(5):  # Search up to 5 levels
                if parent:
                    link = parent.find('a', href=True)
                    if link and link['href'].startswith('/'):
                        comic_link = link['href']
                        break
                    parent = parent.parent
            
            if comic_link:
                # Parse comic slug from link like /beetle-bailey-1/2025-11-15
                parts = comic_link.strip('/').split('/')
                if len(parts) >= 1:
                    comic_slug = parts[0]
                    
                    # Clean up slug and generate name
                    comic_name = comic_slug.replace('-', ' ').title()
                    
                    # Get the actual image URL (remove Next.js optimization)
                    if 'url=' in src:
                        # Extract the actual URL from Next.js image optimization
                        match = re.search(r'url=([^&]+)', src)
                        if match:
                            import urllib.parse
                            actual_url = urllib.parse.unquote(match.group(1))
                            src = actual_url
                    
                    comics.append({
                        'name': comic_name,
                        'slug': comic_slug,
                        'image_url': src,
                        'date': date_str,
                        'url': f"https://comicskingdom.com{comic_link}",
                        'source': 'comicskingdom'
                    })
    
    # Group images by slug (some comics have multiple panels per day)
    unique_comics = {}
    for comic in comics:
        slug = comic['slug']
        if slug in unique_comics:
            # Comic already exists - add this image to the list
            if 'image_urls' not in unique_comics[slug]:
                # Convert single image_url to list
                unique_comics[slug]['image_urls'] = [unique_comics[slug].pop('image_url')]
            unique_comics[slug]['image_urls'].append(comic['image_url'])
        else:
            # First time seeing this comic
            unique_comics[slug] = comic
    
    comics = list(unique_comics.values())
    
    print(f"✅ Extracted {len(comics)} comics from favorites page")
    
    if comics:
        print("\nSample comics:")
        for comic in comics[:5]:
            print(f"  - {comic['name']} ({comic['slug']})")
    
    return comics


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
