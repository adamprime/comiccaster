#!/usr/bin/env python3
"""One-off diagnostic: what is actually on the political favorites page?

Fetches CUSTOM_PAGE_1 (the political favorites page) for a specific date,
saves the rendered HTML, and reports every slug found on the page —
separately for the "updated today" ComicViewer containers and the
"not issued today" FeaturesNotIssued section at the bottom of the page.

Use this to investigate cases where a comic is expected on the favorites
page but isn't appearing in the daily scrape JSON (e.g., issue #138).
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from authenticated_scraper_secure import (
    _COMIC_CONTAINER_RE,
    _COMIC_CONTAINER_SELECTOR,
    _NOT_ISSUED_RE,
    _extract_comic_slug_from_link,
    load_config_from_env,
    login,
)


def render_page(driver, page_url):
    """Fetch the page, wait for containers, scroll to load lazies."""
    print(f"Fetching: {page_url}")
    driver.get(page_url)

    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, _COMIC_CONTAINER_SELECTOR)
        )
    except Exception:
        print("  ⚠️  Comic containers never appeared (waited 20s)")

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    import time
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    return driver.page_source


def extract_slugs(html):
    """Return (updated_slugs, not_issued_slugs) found on the page."""
    soup = BeautifulSoup(html, 'html.parser')

    updated = set()
    for container in soup.find_all('div', class_=_COMIC_CONTAINER_RE):
        for link in container.find_all('a', href=True):
            slug = _extract_comic_slug_from_link(link['href'])
            if slug:
                updated.add(slug)
                break

    not_issued = set()
    for section in soup.find_all('div', class_=_NOT_ISSUED_RE):
        for link in section.find_all('a', href=True):
            slug = _extract_comic_slug_from_link(link['href'])
            if slug:
                not_issued.add(slug)

    return updated, not_issued


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'),
                        help='Target date YYYY-MM-DD (passed as ?date= query param)')
    parser.add_argument('--target-slug', default='nickanderson',
                        help='Slug to flag in the report (default: nickanderson)')
    parser.add_argument('--show-browser', action='store_true',
                        help='Run Chrome non-headless for visual debugging')
    parser.add_argument('--output-dir', default='/tmp',
                        help='Where to save the rendered HTML (default: /tmp)')
    args = parser.parse_args()

    config = load_config_from_env()

    # CUSTOM_PAGE_1 is the political favorites page by convention.
    political_pages = [p for p in config['custom_pages'] if p.get('category') == 'political']
    if not political_pages:
        print("❌ No CUSTOM_PAGE_* with category=political in env")
        return 1
    if len(political_pages) > 1:
        print(f"⚠️  Found {len(political_pages)} political pages; using the first")
    base_url = political_pages[0]['url']
    target_url = f"{base_url}{'&' if '?' in base_url else '?'}date={args.date}"

    options = Options()
    if not args.show_browser:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=options)

    try:
        if not login(driver, config['credentials']['email'], config['credentials']['password']):
            print("❌ Authentication failed")
            return 1

        html = render_page(driver, target_url)
    finally:
        driver.quit()

    out_path = Path(args.output_dir) / f'political_favorites_{args.date}.html'
    out_path.write_text(html)
    print(f"\nSaved HTML to: {out_path} ({len(html):,} bytes)")

    updated, not_issued = extract_slugs(html)
    target = args.target_slug

    print("\n" + "=" * 60)
    print(f"Political favorites page for {args.date}")
    print("=" * 60)
    print(f"\nComicViewer containers (updated today): {len(updated)}")
    for slug in sorted(updated):
        marker = '  ← TARGET' if slug == target else ''
        print(f"  {slug}{marker}")

    print(f"\nFeaturesNotIssued (did NOT update today): {len(not_issued)}")
    for slug in sorted(not_issued):
        marker = '  ← TARGET' if slug == target else ''
        print(f"  {slug}{marker}")

    combined = updated | not_issued
    print(f"\nTOTAL slugs on page: {len(combined)} ({len(updated)} updated + {len(not_issued)} not issued)")

    print("\n" + "=" * 60)
    print(f"Diagnosis for '{target}':")
    print("=" * 60)
    if target in updated:
        print(f"  ✅ Found in ComicViewer (updated). Scraper SHOULD have extracted it.")
        print(f"     → Real extraction bug; inspect HTML around this slug in {out_path}")
    elif target in not_issued:
        print(f"  ℹ️  Found in FeaturesNotIssued (didn't post {args.date}).")
        print(f"     → No scraper bug; just no comic that day. But: if user expected")
        print(f"       a post on this date, the comic's slug on the page might differ")
        print(f"       from {target!r}, or the date param isn't behaving as expected.")
    else:
        print(f"  ❌ Not on the page at all under slug {target!r}.")
        print(f"     → Either the comic isn't on this favorites page, or its slug")
        print(f"       on the page differs. Grep {out_path} for the comic's display name.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
