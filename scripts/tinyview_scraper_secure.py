#!/usr/bin/env python3
"""
Secure authenticated scraper for TinyView.
Uses cookie persistence to avoid daily magic link login.
"""

import sys
import os
import json
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

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


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
    # Email is optional now (only needed for magic link, not for Google SSO)
    email = os.environ.get('TINYVIEW_EMAIL', '')
    
    config = {
        'email': email,
        'cookie_file': Path(get_optional_env_var('TINYVIEW_COOKIE_FILE', 'data/tinyview_cookies.pkl'))
    }
    
    print(f"✅ Loaded configuration from environment")
    if email:
        print(f"   Email: {config['email']}")
    print(f"   Cookie file: {config['cookie_file']}")
    
    return config


def setup_driver(show_browser=False, for_auth=False, use_profile=True):
    """Setup Chrome driver with anti-detection.
    
    Args:
        show_browser: If True, show browser window
        for_auth: If True and show_browser is False, this is for authentication so show warning
        use_profile: If True, use persistent Chrome profile to maintain login state
    """
    options = Options()
    if not show_browser:
        if for_auth:
            print("\n⚠️  WARNING: Running authentication in headless mode")
            print("   You won't be able to interact with the browser")
            print("   Consider running with --show-browser flag\n")
        options.add_argument('--headless=new')
    
    # Use persistent profile directory to maintain login across runs
    if use_profile:
        profile_dir = Path.home() / '.tinyview_chrome_profile'
        profile_dir.mkdir(exist_ok=True)
        options.add_argument(f'--user-data-dir={profile_dir}')
        print(f"🔧 Using Chrome profile: {profile_dir}")
    
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
    """Save authentication cookies and localStorage to file."""
    # Make sure we're on the TinyView domain to get all cookies
    current_url = driver.current_url
    print(f"📍 Current URL: {current_url}")
    
    if 'tinyview.com' not in current_url:
        print("📍 Navigating to TinyView to capture cookies...")
        driver.get("https://tinyview.com")
        time.sleep(3)
    
    # Get cookies
    cookies = driver.get_cookies()
    print(f"   Found {len(cookies)} cookies")
    
    # Get localStorage (TinyView might store auth tokens here)
    try:
        local_storage = driver.execute_script("""
            let items = {};
            for (let i = 0; i < localStorage.length; i++) {
                let key = localStorage.key(i);
                items[key] = localStorage.getItem(key);
            }
            return items;
        """)
        print(f"   Found {len(local_storage)} localStorage items")
        
        # Debug: show what keys we found
        if local_storage:
            print(f"   localStorage keys: {list(local_storage.keys())}")
            # Check for Firebase auth tokens
            firebase_keys = [k for k in local_storage.keys() if 'firebase' in k.lower() or 'auth' in k.lower()]
            if firebase_keys:
                print(f"   ✅ Found Firebase auth keys: {firebase_keys}")
            else:
                print(f"   ⚠️  No Firebase auth keys found - this might be why auth isn't persisting")
    except Exception as e:
        print(f"   Could not access localStorage: {e}")
        local_storage = {}
    
    # Get sessionStorage
    try:
        session_storage = driver.execute_script("""
            let items = {};
            for (let i = 0; i < sessionStorage.length; i++) {
                let key = sessionStorage.key(i);
                items[key] = sessionStorage.getItem(key);
            }
            return items;
        """)
        print(f"   Found {len(session_storage)} sessionStorage items")
    except Exception as e:
        print(f"   Could not access sessionStorage: {e}")
        session_storage = {}
    
    # Save everything
    auth_data = {
        'cookies': cookies,
        'local_storage': local_storage,
        'session_storage': session_storage,
        'timestamp': datetime.now().isoformat()
    }
    
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookie_file, 'wb') as f:
        pickle.dump(auth_data, f)
    
    total_items = len(cookies) + len(local_storage) + len(session_storage)
    print(f"✅ Auth data saved to {cookie_file} ({total_items} total items)")


def load_cookies(driver, cookie_file):
    """Load saved cookies, localStorage, and sessionStorage."""
    if not cookie_file.exists():
        return False
    
    try:
        with open(cookie_file, 'rb') as f:
            auth_data = pickle.load(f)
        
        # Handle old format (just cookies) vs new format (dict with cookies + storage)
        if isinstance(auth_data, list):
            # Old format - just cookies
            cookies = auth_data
            local_storage = {}
            session_storage = {}
        else:
            # New format - dict with cookies and storage
            cookies = auth_data.get('cookies', [])
            local_storage = auth_data.get('local_storage', {})
            session_storage = auth_data.get('session_storage', {})
        
        # Navigate to site first (required before adding cookies and storage)
        print("🌐 Navigating to TinyView to load auth data...")
        try:
            driver.get("https://tinyview.com")
            time.sleep(2)
        except Exception as nav_error:
            print(f"⚠️  Navigation warning: {nav_error}")
        
        # Add all cookies
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"⚠️  Could not add cookie: {e}")
        
        # Restore localStorage
        if local_storage:
            try:
                for key, value in local_storage.items():
                    driver.execute_script(f"localStorage.setItem('{key}', '{value}');")
                print(f"   Restored {len(local_storage)} localStorage items")
            except Exception as e:
                print(f"⚠️  Could not restore localStorage: {e}")
        
        # Restore sessionStorage
        if session_storage:
            try:
                for key, value in session_storage.items():
                    driver.execute_script(f"sessionStorage.setItem('{key}', '{value}');")
                print(f"   Restored {len(session_storage)} sessionStorage items")
            except Exception as e:
                print(f"⚠️  Could not restore sessionStorage: {e}")
        
        total_items = len(cookies) + len(local_storage) + len(session_storage)
        print(f"✅ Loaded auth data from {cookie_file} ({total_items} items)")
        
        # Refresh page to apply auth and wait for Firebase to initialize
        print("🔄 Refreshing page to apply authentication...")
        driver.refresh()
        time.sleep(3)  # Give Firebase more time to initialize
        
        return True
    except Exception as e:
        print(f"❌ Error loading auth data: {e}")
        return False


def is_authenticated(driver, wait_for_auth=False):
    """Check if the current session is authenticated.
    
    Args:
        wait_for_auth: If True, wait up to 10 seconds for auth to initialize
    """
    try:
        current_url = driver.current_url
        if 'tinyview.com' not in current_url:
            driver.get("https://tinyview.com")
        
        # If waiting for auth, give Firebase time to initialize
        if wait_for_auth:
            print("⏳ Waiting for Firebase auth to initialize...")
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(1)
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Check for sign-in button (present if NOT logged in)
                sign_in = soup.find('button', string=lambda x: x and 'sign in' in x.lower() if x else False)
                sign_in_link = soup.find('a', string=lambda x: x and 'sign in' in x.lower() if x else False)
                
                # If no sign-in button, we might be logged in
                if not sign_in and not sign_in_link:
                    # Look for logged-in indicators
                    has_notifications = soup.find('a', href=lambda x: x and 'notifications' in x if x else False)
                    has_user_menu = soup.find('button', {'aria-label': lambda x: x and 'user' in x.lower() if x else False})
                    
                    # Check page text for user-specific content
                    page_text = soup.get_text().lower()
                    has_user_content = 'notifications from creators' in page_text
                    
                    if has_notifications or has_user_menu or has_user_content:
                        print(f"✅ Detected logged-in state (attempt {attempt + 1}/{max_attempts})")
                        return True
                
                if attempt < max_attempts - 1:
                    driver.refresh()
        else:
            time.sleep(3)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Check for sign-in button (present if NOT logged in)
            sign_in = soup.find('button', string=lambda x: x and 'sign in' in x.lower() if x else False)
            sign_in_link = soup.find('a', string=lambda x: x and 'sign in' in x.lower() if x else False)
            
            if sign_in or sign_in_link:
                return False
            
            # Look for profile/user menu (present if logged in)
            has_notifications = soup.find('a', href=lambda x: x and 'notifications' in x if x else False)
            has_user_menu = soup.find('button', {'aria-label': lambda x: x and 'user' in x.lower() if x else False})
            
            # Check page text for user-specific content
            page_text = soup.get_text().lower()
            has_user_content = 'notifications from creators' in page_text
            
            if has_notifications or has_user_menu or has_user_content:
                print("✅ Detected logged-in state (found user UI elements)")
                return True
        
        return False
        
    except Exception as e:
        print(f"⚠️  Error checking authentication: {e}")
        return False


def login_with_google_sso(driver):
    """Login to TinyView using Google SSO."""
    print("\n" + "="*80)
    print("TINYVIEW GOOGLE SSO LOGIN")
    print("="*80)
    print("Navigating to TinyView...")
    
    driver.get("https://tinyview.com")
    time.sleep(3)
    
    try:
        # Look for sign in button/link
        print("Looking for sign in button...")
        
        # Try multiple selectors for the sign-in button
        sign_in_button = None
        selectors = [
            (By.LINK_TEXT, "Sign In"),
            (By.PARTIAL_LINK_TEXT, "Sign In"),
            (By.XPATH, "//button[contains(text(), 'Sign')]"),
            (By.XPATH, "//a[contains(text(), 'Sign')]"),
        ]
        
        for selector_type, selector_value in selectors:
            try:
                sign_in_button = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                if sign_in_button:
                    break
            except:
                continue
        
        if sign_in_button:
            print("✅ Found sign in button, clicking...")
            driver.execute_script("arguments[0].click();", sign_in_button)
            time.sleep(5)  # Wait longer for signin page to load
            print(f"   Current URL after clicking: {driver.current_url}")
        
        # Look for "Sign in with Google" button
        print("Looking for 'Sign in with Google' button...")
        
        # Wait for Google button to appear
        google_button = None
        google_selectors = [
            (By.XPATH, "//button[contains(text(), 'Google')]"),
            (By.XPATH, "//button[contains(text(), 'google')]"),
            (By.XPATH, "//*[contains(text(), 'Sign in with Google')]"),
            (By.XPATH, "//*[contains(text(), 'Google')]"),
            (By.CSS_SELECTOR, "button[aria-label*='Google']"),
        ]
        
        for selector_type, selector_value in google_selectors:
            try:
                google_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                if google_button:
                    print(f"✅ Found Google button: {google_button.text}")
                    break
            except:
                continue
        
        if not google_button:
            print("❌ Could not find 'Sign in with Google' button automatically")
            print(f"   Current URL: {driver.current_url}")
            
            # Try to debug what's on the page
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            buttons = soup.find_all('button')
            print(f"   Found {len(buttons)} buttons on page:")
            for btn in buttons[:10]:  # Show first 10 buttons
                btn_text = btn.get_text(strip=True)
                if btn_text:
                    print(f"     - {btn_text[:50]}")
            
            print("\n⏸️  Please manually click the 'Sign in with Google' button in the browser")
            print("   Waiting 60 seconds for you to complete this step...")
            time.sleep(60)
            
            # After manual click, continue with auth check
            google_button = True  # Fake it since user did it manually
        
        # Click Google SSO button (if we found it)
        if google_button and google_button is not True:
            print("Clicking 'Sign in with Google' button...")
            driver.execute_script("arguments[0].click();", google_button)
            time.sleep(3)
        
        # Wait for user to complete Google authentication
        print("\n" + "="*80)
        print("⏸️  PLEASE COMPLETE THE GOOGLE LOGIN")
        print("="*80)
        print("Instructions:")
        print("  1. Select your Google account in the browser window")
        print("  2. If prompted, click 'Continue' or 'Allow'")
        print("  3. Wait for the browser to redirect back to TinyView")
        print("\n⏳ Waiting for you to complete Google login...")
        print("   This script will detect when you're logged in")
        print("="*80 + "\n")
        
        # Poll for authentication every 3 seconds for up to 3 minutes
        for i in range(60):  # 60 * 3 seconds = 3 minutes
            time.sleep(3)
            
            if is_authenticated(driver):
                print(f"\n✅ Login successful! You are now authenticated.")
                
                # Navigate to TinyView homepage to ensure cookies are set
                print("📍 Navigating to TinyView homepage...")
                driver.get("https://tinyview.com")
                time.sleep(3)  # Give page time to fully load
                return True
            
            if (i+1) % 10 == 0:  # Every 30 seconds
                print(f"  ...still waiting ({(i+1)*3}/180 seconds)...")
        
        print("\n❌ Timeout waiting for login")
        return False
        
    except Exception as e:
        print(f"❌ Login failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def extract_notifications(driver):
    """Extract recent comic updates from the notifications sidebar on homepage."""
    print(f"\n{'='*80}")
    print(f"Extracting notifications from TinyView")
    print("="*80)
    
    # Go to homepage where notifications sidebar is visible
    driver.get("https://tinyview.com")
    time.sleep(5)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Parse notifications
    notifications = []
    seen_urls = set()
    
    # Find the notifications section
    # Look for text containing "Notifications from creators"
    notifications_section = soup.find('p', string=lambda x: x and 'Notifications from creators' in x if x else False)
    
    if notifications_section:
        # Navigate up to the parent section containing all notifications
        notifications_container = notifications_section.find_parent('section')
        if not notifications_container:
            # Try finding by section with specific classes
            notifications_container = soup.find('section', class_=lambda x: x and 'mx-4' in x if x else False)
        
        if notifications_container:
            print("✅ Found notifications container")
            
            # Debug: show what's in the container
            container_text = notifications_container.get_text()[:200]
            print(f"   Container preview: {container_text}...")
            
            # Find all links within the notifications container
            notification_links = notifications_container.find_all('a', href=True)
            print(f"   Found {len(notification_links)} links in container")
            
            # Debug: show first few links
            for i, link in enumerate(notification_links[:5]):
                print(f"   Link {i+1}: {link.get('href', 'no href')}")
            
            for link in notification_links:
                href = link.get('href', '')
                
                # Look for links to specific comic strips
                # Format: /comic-slug/YYYY/MM/DD/strip-title
                if href.startswith('/') and href.count('/') >= 4:
                    parts = href.strip('/').split('/')
                    
                    # Parse comic URL structure
                    if len(parts) >= 5:
                        comic_slug = parts[0]
                        try:
                            year, month, day = parts[1], parts[2], parts[3]
                            title_slug = '-'.join(parts[4:])
                            
                            full_url = f"https://tinyview.com{href}"
                            
                            # Skip if we've already seen this URL
                            if full_url in seen_urls:
                                continue
                            seen_urls.add(full_url)
                            
                            # Get the full text content of this notification
                            # Look for parent div/element that contains the whole notification
                            notif_parent = link.find_parent('div')
                            if notif_parent:
                                notif_text = notif_parent.get_text(strip=True)
                                
                                # Extract comic name - usually before "published"
                                comic_name = comic_slug.replace('-', ' ').title()
                                if 'published' in notif_text:
                                    name_part = notif_text.split('published')[0].strip()
                                    if name_part:
                                        comic_name = name_part
                                
                                # Extract timestamp - look for "ago" pattern
                                timestamp = None
                                for word in notif_text.split():
                                    if 'ago' in word:
                                        # Get the time value before "ago"
                                        words = notif_text.split()
                                        ago_idx = words.index(word)
                                        if ago_idx > 0:
                                            timestamp = f"{words[ago_idx-1]} {word}"
                                            break
                                
                                # Extract title from the notification text
                                # Usually in brackets like [Title] "description"
                                import re
                                title_match = re.search(r'\[(.*?)\]', notif_text)
                                episode_title = title_match.group(1) if title_match else title_slug.replace('-', ' ').title()
                                
                                notification = {
                                    'comic_slug': comic_slug,
                                    'comic_name': comic_name,
                                    'date': f"{year}/{month}/{day}",
                                    'title': episode_title,
                                    'title_slug': title_slug,
                                    'url': full_url,
                                    'timestamp': timestamp,
                                    'source': 'tinyview'
                                }
                                
                                notifications.append(notification)
                                print(f"  Found: {notification['comic_name']} - {notification['date']} ({notification['timestamp'] or 'no timestamp'})")
                                
                        except (ValueError, IndexError) as e:
                            continue
    else:
        print("⚠️  Could not find notifications container")
        print("    The page structure may have changed or you may not be logged in")
    
    print(f"\n✅ Extracted {len(notifications)} notifications")
    return notifications


def discover_all_comics(driver):
    """Discover all comics the user follows from their profile/notifications."""
    print(f"\n{'='*80}")
    print(f"Discovering all followed comics")
    print("="*80)
    
    # Navigate to notifications to see all followed comics
    notifications = extract_notifications(driver)
    
    # Extract unique comics
    comics_dict = {}
    for notif in notifications:
        slug = notif['comic_slug']
        if slug not in comics_dict:
            comics_dict[slug] = {
                'name': notif['comic_name'],
                'slug': slug,
                'url': f"https://tinyview.com/{slug}",
                'source': 'tinyview'
            }
    
    comics = list(comics_dict.values())
    print(f"\n✅ Discovered {len(comics)} unique comics from notifications")
    
    return comics


def authenticate_with_cookie_persistence(driver, config, show_browser=False, force_reauth=False):
    """Authenticate using saved cookies or Google SSO login."""
    cookie_file = config['cookie_file']
    
    # Check if running in CI environment
    is_ci = os.getenv('CI') == 'true' or os.getenv('GITHUB_ACTIONS') == 'true'
    
    # If force_reauth, skip cookie loading
    if force_reauth and cookie_file.exists():
        print("🗑️  Skipping saved cookies (force re-auth)")
    elif cookie_file.exists():
        # Check cookie age
        cookie_age_days = (datetime.now() - datetime.fromtimestamp(
            cookie_file.stat().st_mtime
        )).days
        print(f"📅 Cookie file is {cookie_age_days} days old")
        
        if cookie_age_days > 30:
            print(f"⚠️  Cookies are old. Recommend re-authentication.")
        
        # Try to load existing cookies
        if load_cookies(driver, cookie_file):
            if is_ci:
                # In CI, skip verification to avoid timeout issues
                print("✅ Running in CI - trusting saved cookies without verification")
                return True
            
            # Check if cookies are still valid (local only)
            print("🔍 Checking if auth data is still valid...")
            
            if is_authenticated(driver, wait_for_auth=True):
                print("✅ Successfully authenticated with saved auth data!")
                return True
            else:
                print("⚠️  Saved auth data is expired or invalid")
    
    # Need to login
    if is_ci:
        print("❌ Authentication failed in CI environment")
        print("Cookies may be expired. Run re-authentication locally and update GitHub Secret.")
        return False
    
    # If browser is visible, offer to authenticate now
    if show_browser:
        print("\n🔐 Authentication required")
        print("Will now attempt Google SSO login...")
        
        if login_with_google_sso(driver):
            # Save cookies for future use
            save_cookies(driver, cookie_file)
            print("✅ Login successful and cookies saved!")
            return True
        else:
            print("❌ Login failed")
            return False
    else:
        # Headless mode - can't authenticate
        print("\n❌ Cookies expired or invalid - re-authentication required")
        print("\nTo re-authenticate, run:")
        print("  python3 tinyview_scraper_secure.py --show-browser")
        print("\nThis will open a browser so you can complete the Google login.")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Secure authenticated scraper for TinyView with cookie persistence'
    )
    parser.add_argument('--show-browser', action='store_true', help='Show browser window (required for authentication)')
    parser.add_argument('--force-reauth', action='store_true', help='Force re-authentication (ignore saved cookies)')
    parser.add_argument('--discover-comics', action='store_true', help='Discover all followed comics')
    parser.add_argument('--get-notifications', action='store_true', help='Get recent notifications')
    parser.add_argument('--output-dir', default='data', help='Output directory for JSON files')
    parser.add_argument('--test-auth', action='store_true', help='Test if cookies are still valid')
    parser.add_argument('--no-profile', action='store_true', help='Do not use persistent Chrome profile (for testing)')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load configuration from environment
    config = load_config_from_env()
    
    # Delete cookies if forced re-auth
    if args.force_reauth and config['cookie_file'].exists():
        config['cookie_file'].unlink()
        print("🗑️  Deleted saved cookies (force re-auth)")
    
    # Setup Chrome with persistent profile (unless disabled)
    use_profile = not args.no_profile
    driver = setup_driver(show_browser=args.show_browser, use_profile=use_profile)
    
    try:
        # Test authentication only
        if args.test_auth:
            if authenticate_with_cookie_persistence(driver, config, show_browser=False, force_reauth=False):
                print("\n✅ Authentication successful! Cookies are valid.")
                driver.quit()
                return 0
            else:
                print("\n❌ Authentication failed. Cookies may be expired.")
                driver.quit()
                return 1
        
        # Authenticate (with cookie persistence)
        if not authenticate_with_cookie_persistence(driver, config, 
                                                    show_browser=args.show_browser, 
                                                    force_reauth=args.force_reauth):
            print("❌ Authentication failed")
            driver.quit()
            return 1
        
        # Discover comics if requested
        if args.discover_comics:
            comics = discover_all_comics(driver)
            
            if comics:
                output_file = output_dir / 'tinyview_discovered_comics.json'
                with open(output_file, 'w') as f:
                    json.dump(comics, f, indent=2)
                
                print(f"\n💾 Saved {len(comics)} discovered comics to {output_file}")
        
        # Get notifications if requested
        if args.get_notifications:
            notifications = extract_notifications(driver)
            
            if notifications:
                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                output_file = output_dir / f'tinyview_notifications_{timestamp}.json'
                with open(output_file, 'w') as f:
                    json.dump(notifications, f, indent=2)
                
                print(f"\n💾 Saved {len(notifications)} notifications to {output_file}")
        
        print(f"\n{'='*80}")
        print("✅ SUCCESS!")
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
