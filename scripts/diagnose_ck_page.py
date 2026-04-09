#!/usr/bin/env python3
"""
Diagnostic script for Comics Kingdom favorites page.
Captures screenshots and HTML snapshots at each stage to debug extraction failures.
"""

import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path

# Reuse auth machinery from the main scraper
sys.path.insert(0, str(Path(__file__).parent))
from comicskingdom_scraper_secure import (
    load_config_from_env, setup_driver, load_cookies, is_authenticated
)


def save_snapshot(driver, output_dir, label):
    """Save screenshot + HTML snapshot with a descriptive label."""
    timestamp = datetime.now().strftime('%H%M%S')
    prefix = f"{timestamp}_{label}"

    screenshot_path = output_dir / f"{prefix}.png"
    html_path = output_dir / f"{prefix}.html"

    driver.save_screenshot(str(screenshot_path))
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(driver.page_source)

    print(f"  Saved: {screenshot_path.name} + {html_path.name}")
    return html_path


def summarize_page(driver):
    """Print a quick summary of what's on the page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    print(f"  URL: {driver.current_url}")
    print(f"  Title: {driver.title}")

    # Count elements
    all_imgs = soup.find_all('img')
    all_anchors = soup.find_all('a', href=True)
    all_buttons = soup.find_all('button')
    print(f"  <img>: {len(all_imgs)}, <a>: {len(all_anchors)}, <button>: {len(all_buttons)}")

    # Look for common modal/popup indicators
    modal_candidates = []
    for attr in ['class', 'id', 'role']:
        for el in soup.find_all(attrs={attr: True}):
            val = str(el.get(attr, '')).lower()
            if any(kw in val for kw in ['modal', 'popup', 'overlay', 'dialog', 'consent', 'banner', 'interstitial', 'dismiss', 'close']):
                tag = el.name
                modal_candidates.append(f"<{tag} {attr}=\"{el.get(attr)}\">")
    if modal_candidates:
        print(f"  Possible modals/popups ({len(modal_candidates)}):")
        for m in modal_candidates[:15]:
            print(f"    {m}")
    else:
        print("  No obvious modal/popup elements detected by class/id/role scan")

    # Check for images matching CK comic domains
    from urllib.parse import urlparse
    ck_imgs = []
    for img in all_imgs:
        src = img.get('src', '')
        try:
            parsed = urlparse(src)
            if parsed.netloc == 'wp.comicskingdom.com' or parsed.netloc.endswith('.comicskingdom.com'):
                ck_imgs.append(src[:120])
        except Exception:
            pass
    print(f"  CK-domain images: {len(ck_imgs)}")
    if ck_imgs:
        for u in ck_imgs[:5]:
            print(f"    {u}")

    # Check for comic-card-like link patterns (/<slug>/<date>)
    import re
    comic_links = [a['href'] for a in all_anchors
                   if re.match(r'^/[a-z0-9-]+/\d{4}-\d{2}-\d{2}', a['href'])]
    print(f"  Comic-style links (/<slug>/<date>): {len(comic_links)}")
    if comic_links:
        for lnk in comic_links[:5]:
            print(f"    {lnk}")

    return soup


def try_dismiss_popups(driver):
    """Attempt common popup dismissal strategies."""
    from selenium.webdriver.common.by import By

    strategies = [
        ("CSS: button with 'close' in class", "button[class*='close'], button[class*='Close']"),
        ("CSS: button with 'dismiss' in class", "button[class*='dismiss'], button[class*='Dismiss']"),
        ("CSS: [aria-label*='close']", "[aria-label*='close'], [aria-label*='Close']"),
        ("CSS: [role='dialog'] button", "[role='dialog'] button"),
        ("CSS: .modal button", ".modal button, .modal-close, .modal__close"),
        ("CSS: overlay close", ".overlay-close, .popup-close, .consent-close"),
        ("XPath: button containing 'close' text", None),  # handled separately
        ("XPath: button containing 'accept' text", None),
        ("XPath: button containing 'got it' text", None),
        ("XPath: button containing 'no thanks' text", None),
    ]

    clicked = []
    for label, selector in strategies:
        try:
            if selector:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            elif 'close' in label.lower() and 'text' in label.lower():
                elements = driver.find_elements(By.XPATH, "//button[contains(translate(., 'CLOSE', 'close'), 'close')]")
            elif 'accept' in label.lower():
                elements = driver.find_elements(By.XPATH, "//button[contains(translate(., 'ACCEPT', 'accept'), 'accept')]")
            elif 'got it' in label.lower():
                elements = driver.find_elements(By.XPATH, "//button[contains(translate(., 'GOT IT', 'got it'), 'got it')]")
            elif 'no thanks' in label.lower():
                elements = driver.find_elements(By.XPATH, "//button[contains(translate(., 'NO THANKS', 'no thanks'), 'no thanks')]")
            else:
                continue

            for el in elements:
                if el.is_displayed():
                    text = el.text.strip()[:50]
                    print(f"  Clicking: {label} -> \"{text}\"")
                    el.click()
                    clicked.append(label)
                    time.sleep(1)
        except Exception as e:
            pass

    if not clicked:
        print("  No clickable popup elements found with standard strategies")
    return clicked


def main():
    output_dir = Path('data/ck_diagnostics')
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config_from_env()
    driver = setup_driver(show_browser=True)

    try:
        # Phase 1: Load cookies and authenticate
        print("\n=== Phase 1: Authentication ===")
        if not load_cookies(driver, config['cookie_file']):
            print("No cookies loaded. Exiting (run reauth first).")
            return 1

        if not is_authenticated(driver):
            print("Authentication failed. Exiting.")
            return 1
        print("Authenticated successfully.")

        # Phase 2: Navigate to favorites and snapshot BEFORE any interaction
        print("\n=== Phase 2: Initial page state ===")
        driver.get("https://comicskingdom.com/favorites")
        time.sleep(5)
        save_snapshot(driver, output_dir, "01_initial_load")
        summarize_page(driver)

        # Phase 3: Try to dismiss popups
        print("\n=== Phase 3: Popup dismissal ===")
        clicked = try_dismiss_popups(driver)
        if clicked:
            time.sleep(2)
            save_snapshot(driver, output_dir, "02_after_popup_dismiss")
            summarize_page(driver)

        # Phase 4: Scroll to load lazy content
        print("\n=== Phase 4: After scrolling ===")
        for i in range(8):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        save_snapshot(driver, output_dir, "03_after_scroll")
        summarize_page(driver)

        # Phase 5: Try popup dismissal again (some appear after scroll)
        print("\n=== Phase 5: Second popup check ===")
        clicked2 = try_dismiss_popups(driver)
        if clicked2:
            time.sleep(2)
            save_snapshot(driver, output_dir, "04_after_second_dismiss")
            summarize_page(driver)

        print(f"\n=== Done! Snapshots saved to {output_dir}/ ===")
        print("Review the .png screenshots and .html files to identify:")
        print("  1. What popup/modal is showing")
        print("  2. What the comic card DOM structure looks like")
        print("  3. Whether comic images use CK domains or a new CDN")

        # Keep browser open for manual inspection
        print("\nBrowser left open for manual inspection. Press Enter to close...")
        input()

    finally:
        driver.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
