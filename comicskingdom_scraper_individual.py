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


def get_required_env_var(name):
    """Get required environment variable or exit with error."""
    value = os.environ.get(name)
    if not value:
        print(f"❌ Error: Required environment variable {name} is not set")
        sys.exit(1)
    return value


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


def get_optional_env_var(name, default):
    """Get optional environment variable with default."""
    return os.environ.get(name, default)


def setup_driver(show_browser=False):
    """Setup Chrome driver."""
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
        driver.get("https://comicskingdom.com")
        time.sleep(2)
        
        # Add all cookies
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                pass
        
        print(f"✅ Loaded cookies from {cookie_file}")
        return True
    except Exception as e:
        print(f"❌ Error loading cookies: {e}")
        return False


def is_authenticated(driver):
    """Check if the current session is authenticated."""
    try:
        driver.get("https://comicskingdom.com/favorites")
        time.sleep(2)
        
        if 'login' in driver.current_url:
            return False
        
        return True
    except Exception as e:
        return False


def authenticate_with_cookies(driver, config):
    """Authenticate using saved cookies."""
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
    url = f"https://comicskingdom.com/{comic_slug}/{date_str}"
    
    try:
        driver.get(url)
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
    
    args = parser.parse_args()
    
    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load configuration
    config = load_config_from_env()
    
    # Load comics catalog
    comics = load_comics_catalog()
    
    # Setup Chrome
    driver = setup_driver(show_browser=args.show_browser)
    
    try:
        # Authenticate
        if not authenticate_with_cookies(driver, config):
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
