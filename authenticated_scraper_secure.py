#!/usr/bin/env python3
"""
Secure authenticated scraper for GoComics.
Loads all sensitive configuration from environment variables.
"""

import sys
import os
import json
import re
import argparse
from datetime import datetime
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
            'email': get_required_env_var('GOCOMICS_EMAIL'),
            'password': get_required_env_var('GOCOMICS_PASSWORD'),
        },
        'custom_pages': []
    }
    
    # Load custom page URLs from environment
    # Expected format: CUSTOM_PAGE_1, CUSTOM_PAGE_2, etc.
    page_num = 1
    while True:
        page_var = f'CUSTOM_PAGE_{page_num}'
        page_url = os.environ.get(page_var)
        if not page_url:
            break
        
        # Optional: category for this page
        category_var = f'CUSTOM_PAGE_{page_num}_CATEGORY'
        category = os.environ.get(category_var, 'daily')
        
        config['custom_pages'].append({
            'url': page_url,
            'category': category,
            'index': page_num
        })
        page_num += 1
    
    if not config['custom_pages']:
        print("❌ Error: No custom pages configured. Set CUSTOM_PAGE_1, CUSTOM_PAGE_2, etc.")
        sys.exit(1)
    
    print(f"✅ Loaded {len(config['custom_pages'])} custom page URLs from environment")
    
    return config


def login(driver, email, password):
    """Login via OAuth and return success status."""
    # OAuth URL loaded from environment for security
    oauth_base = get_optional_env_var('OAUTH_BASE_URL', 
        'https://amub2c.b2clogin.com/amub2c.onmicrosoft.com/b2c_1a_gc_signinsignout_policies/oauth2/v2.0/authorize')
    
    oauth_params = get_optional_env_var('OAUTH_PARAMS',
        'client_id=6cf955a1-f547-4eb9-aa62-f069cabf6ead'
        '&scope=https%3A%2F%2Famub2c.onmicrosoft.com%2Fapi%2Fdemo.read%20'
        'https%3A%2F%2Famub2c.onmicrosoft.com%2Fapi%2Fdemo.write%20'
        'https%3A%2F%2Famub2c.onmicrosoft.com%2Fapi%2Fuser_impersonation%20'
        'offline_access%20openid'
        '&response_type=code'
        '&redirect_uri=https%3A%2F%2Fwww.gocomics.com%2Fapi%2Fauth%2Fcallback%2Fazureb2c'
        '&domain_hint=signin'
        '&referrer_url=https%3A%2F%2Fwww.gocomics.com%2F'
        '&_ga=false')
    
    oauth_url = f"{oauth_base}?{oauth_params}"
    
    print("Logging in...")
    driver.get(oauth_url)
    time.sleep(3)
    
    try:
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "signInName"))
        )
        password_field = driver.find_element(By.ID, "password")
        
        email_field.send_keys(email)
        password_field.send_keys(password)
        
        submit_button = driver.find_element(By.ID, "continue")
        submit_button.click()
        
        time.sleep(5)
        
        # Verify login success
        if 'gocomics.com' in driver.current_url:
            print("✅ Login successful")
            return True
        else:
            print("❌ Login may have failed")
            return False
            
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False


def extract_comics_from_page(driver, page_url, date_str):
    """Extract comics from a custom page."""
    print(f"\nScraping: {page_url}")
    driver.get(page_url)
    time.sleep(5)
    
    # Scroll to load lazy images
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    all_imgs = soup.find_all('img')
    
    badges = []
    strips = []
    
    for img in all_imgs:
        src = img.get('src', '')
        
        # Extract comic names from badge images
        if 'Badge' in src and 'Global_Feature_Badge' in src:
            match = re.search(r'Badge_([^_]+(?:_[^_]+)*?)_600', src)
            if match:
                name_part = match.group(1).replace('_', ' ')
                badges.append({'name': name_part})
        
        # Extract comic strip images
        elif 'featureassets.gocomics.com' in src and 'Badge' not in src:
            strips.append({'image_url': src})
    
    # Match badges to strips
    comics = []
    match_count = min(len(badges), len(strips))
    
    for i in range(match_count):
        badge = badges[i]
        strip = strips[i]
        
        slug = badge['name'].lower().replace(' ', '-').replace('.', '')
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        slug = re.sub(r'\-+', '-', slug).strip('-')
        
        comics.append({
            'name': badge['name'],
            'slug': slug,
            'image_url': strip['image_url'],
            'date': date_str,
            'url': f"https://www.gocomics.com/{slug}/{date_str.replace('-', '/')}",
        })
    
    print(f"  Extracted {len(comics)} comics")
    return comics


def main():
    parser = argparse.ArgumentParser(
        description='Secure authenticated scraper for GoComics'
    )
    parser.add_argument('--date', help='Date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--output-dir', default='/tmp', help='Output directory for JSON files')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window')
    
    args = parser.parse_args()
    
    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load configuration from environment
    config = load_config_from_env()
    
    # Setup Chrome
    options = Options()
    if not args.show_browser:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Login (fresh each run - no cookie storage)
        if not login(driver, config['credentials']['email'], config['credentials']['password']):
            print("❌ Authentication failed")
            driver.quit()
            return 1
        
        # Extract comics from all pages
        all_comics = []
        
        for page in config['custom_pages']:
            comics = extract_comics_from_page(driver, page['url'], date_str)
            
            # Add category metadata
            for comic in comics:
                comic['category'] = page['category']
            
            all_comics.extend(comics)
        
        # Save results
        output_file = output_dir / f'comics_{date_str}.json'
        with open(output_file, 'w') as f:
            json.dump(all_comics, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"✅ SUCCESS! Extracted {len(all_comics)} comics for {date_str}")
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
