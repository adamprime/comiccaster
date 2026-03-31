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
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time


# CSS class patterns used to locate elements on profile pages.
_COMIC_CONTAINER_SELECTOR = '[class*="ComicViewer"]'
_COMIC_CONTAINER_RE = re.compile(r'ComicViewer')
_NOT_ISSUED_RE = re.compile(r'FeaturesNotIssued')


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
        
        # Verify login success - properly validate the domain
        parsed_url = urlparse(driver.current_url)
        # Check that hostname is gocomics.com or a subdomain of gocomics.com
        if parsed_url.netloc == 'gocomics.com' or parsed_url.netloc.endswith('.gocomics.com'):
            print("✅ Login successful")
            return True
        else:
            print(f"❌ Login may have failed - unexpected URL: {driver.current_url}")
            return False
            
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False


def _extract_comic_slug_from_link(href):
    """Extract a comic slug from a link href, handling both absolute and relative URLs.

    Returns the slug string, or None if the link isn't a comic page.
    """
    parsed = urlparse(href)

    is_absolute_gc = (
        parsed.netloc in ('www.gocomics.com', 'gocomics.com')
        or parsed.netloc.endswith('.gocomics.com')
    )
    is_relative = (
        not parsed.netloc
        and href.startswith('/')
        and not href.startswith('//')
    )

    if not is_absolute_gc and not is_relative:
        return None

    if '/profile/' in href or '/_next/' in href or href.startswith('/api/'):
        return None

    slug = parsed.path.strip('/')
    return slug if slug else None


def _get_image_src(img):
    """Extract the best image URL from an img tag, checking src and srcset."""
    src = img.get('src', '')
    if src and 'featureassets.gocomics.com' in src:
        return src

    srcset = img.get('srcset', '')
    if srcset and 'featureassets.gocomics.com' in srcset:
        # Pick the highest-resolution entry from the srcset
        entries = [e.strip().split() for e in srcset.split(',') if 'featureassets' in e]
        if entries:
            return entries[-1][0]

    return src


def _get_badge_name(img):
    """Extract the badge display name from a badge image's src or srcset."""
    for attr in ('src', 'srcset'):
        val = img.get(attr, '')
        if 'Badge' in val and 'Global_Feature_Badge' in val:
            match = re.search(r'Badge_([^_]+(?:_[^_]+)*?)_600', val)
            if match:
                return match.group(1).replace('_', ' ')
    return None


def extract_comics_from_page(driver, page_url, date_str):
    """Extract comics from a custom/profile page.

    Pairs each comic's badge, strip image, and canonical link by finding
    them within the same container element on the page.
    """
    print(f"\nScraping: {page_url}")
    driver.get(page_url)
    time.sleep(5)

    # Wait for comic containers to render before scrolling.
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, _COMIC_CONTAINER_SELECTOR)
        )
    except Exception:
        print("  ⚠️  Comic containers not found after waiting")

    # Scroll to load lazy images
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    containers = soup.find_all('div', class_=_COMIC_CONTAINER_RE)

    if not containers:
        debug_file = Path(f'/tmp/gocomics_debug_{date_str}.html')
        debug_file.write_text(driver.page_source)
        print(f"  ⚠️  No comic containers found. Page source saved to {debug_file}")
    comics = []
    no_link_count = 0
    no_strip_count = 0

    for container in containers:
        # 1. Find the canonical GoComics link inside this container.
        # Links may be absolute (browser-saved HTML) or relative (Selenium).
        slug = None
        for link in container.find_all('a', href=True):
            slug = _extract_comic_slug_from_link(link['href'])
            if slug:
                break
        if not slug:
            no_link_count += 1
            continue

        # 2. Find the strip image inside this container
        strip_url = None
        for img in container.find_all('img'):
            src = _get_image_src(img)
            if src and 'featureassets.gocomics.com' in src and 'Badge' not in src:
                try:
                    parsed_src = urlparse(src)
                    if (parsed_src.netloc == 'featureassets.gocomics.com'
                            or parsed_src.netloc.endswith('.gocomics.com')):
                        strip_url = src
                        break
                except Exception:
                    continue

        if not strip_url:
            no_strip_count += 1
            continue

        # 3. Extract a display name from the badge (nice-to-have, not used for slug)
        badge_name = None
        for img in container.find_all('img'):
            badge_name = _get_badge_name(img)
            if badge_name:
                break

        display_name = badge_name or slug.replace('-', ' ').title()

        comics.append({
            'name': display_name,
            'slug': slug,
            'image_url': strip_url,
            'date': date_str,
            'url': f"https://www.gocomics.com/{slug}/{date_str.replace('-', '/')}",
        })

    # Deduplicate within this page (responsive layout may render each comic
    # in multiple containers, e.g. desktop + mobile variants).
    seen = set()
    unique_comics = []
    for comic in comics:
        if comic['slug'] not in seen:
            seen.add(comic['slug'])
            unique_comics.append(comic)

    responsive_dupes = len(comics) - len(unique_comics)



    # --- Validation: cross-check extraction against page metadata ---
    # The page lists updated comics in the main section and non-updated
    # comics in a separate section at the bottom.
    not_issued_sections = soup.find_all('div', class_=_NOT_ISSUED_RE)
    not_issued_slugs = set()
    for section in not_issued_sections:
        for link in section.find_all('a', href=True):
            slug_val = _extract_comic_slug_from_link(link['href'])
            if slug_val:
                not_issued_slugs.add(slug_val)

    # Count updated comics from containers that have a GoComics link
    # (includes those without a strip image — they still "updated").
    expected_updated = set()
    for container in containers:
        for link in container.find_all('a', href=True):
            slug_val = _extract_comic_slug_from_link(link['href'])
            if slug_val:
                if slug_val not in not_issued_slugs:
                    expected_updated.add(slug_val)
                break

    extracted_slugs = {c['slug'] for c in unique_comics}
    missed = expected_updated - extracted_slugs

    print(f"  Extracted {len(unique_comics)} comics"
          + (f" ({responsive_dupes} responsive duplicates removed)" if responsive_dupes else ""))
    print(f"  Page reports: {len(expected_updated)} updated, {len(not_issued_slugs)} not updated today")

    if missed:
        print(f"  ⚠️  {len(missed)} updated comics not extracted: {', '.join(sorted(missed))}")
    elif expected_updated:
        print(f"  ✅ Extraction matches page — all {len(expected_updated)} updated comics captured")

    return unique_comics


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
        
        # Deduplicate across pages — the same comic may appear on multiple
        # profile pages. Keep the first occurrence.
        seen_slugs = set()
        deduped_comics = []
        cross_page_dupes = 0
        for comic in all_comics:
            slug = comic.get('slug')
            if slug in seen_slugs:
                cross_page_dupes += 1
                continue
            seen_slugs.add(slug)
            deduped_comics.append(comic)

        if cross_page_dupes:
            print(f"\n⚠️  Removed {cross_page_dupes} cross-page duplicate entries")

        all_comics = deduped_comics

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
