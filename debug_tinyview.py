#!/usr/bin/env python3
"""
Debug script to understand Tinyview's structure
This script will save the HTML and take screenshots for analysis
"""

import os
from datetime import datetime
from urllib.parse import urlparse
from comiccaster.tinyview_scraper import TinyviewScraper
from selenium.webdriver.common.by import By
import time

def debug_tinyview():
    """Debug Tinyview structure by saving HTML and analyzing elements."""
    scraper = TinyviewScraper()
    scraper.setup_driver()
    
    # Create debug output directory
    debug_dir = "debug_tinyview"
    os.makedirs(debug_dir, exist_ok=True)
    
    # Test URL for Nick Anderson
    test_url = "https://tinyview.com/nick-anderson/2025/01/17/cartoon"
    
    print(f"Loading: {test_url}")
    scraper.driver.get(test_url)
    
    # Wait for page to load
    print("Waiting for page to load...")
    time.sleep(5)
    
    # Save the HTML
    html_file = os.path.join(debug_dir, "nick_anderson_page.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(scraper.driver.page_source)
    print(f"Saved HTML to: {html_file}")
    
    # Take a screenshot
    screenshot_file = os.path.join(debug_dir, "nick_anderson_screenshot.png")
    scraper.driver.save_screenshot(screenshot_file)
    print(f"Saved screenshot to: {screenshot_file}")
    
    # Analyze the page
    print("\n=== Page Analysis ===")
    
    # Find all images
    all_images = scraper.driver.find_elements(By.TAG_NAME, "img")
    print(f"\nFound {len(all_images)} total images")
    
    # Look for CDN images
    cdn_images = []
    for img in all_images:
        src = img.get_attribute('src') or ''
        data_src = img.get_attribute('data-src') or ''
        
        # Parse URLs to check hostname properly (prevent substring matching attacks)
        src_is_cdn = False
        data_src_is_cdn = False
        
        try:
            if src:
                parsed_src = urlparse(src)
                src_is_cdn = parsed_src.hostname == 'cdn.tinyview.com'
        except:
            pass
            
        try:
            if data_src:
                parsed_data_src = urlparse(data_src)
                data_src_is_cdn = parsed_data_src.hostname == 'cdn.tinyview.com'
        except:
            pass
        
        if src_is_cdn or data_src_is_cdn:
            cdn_images.append({
                'src': src,
                'data-src': data_src,
                'alt': img.get_attribute('alt'),
                'class': img.get_attribute('class'),
                'id': img.get_attribute('id')
            })
    
    print(f"\nFound {len(cdn_images)} CDN images:")
    for i, img in enumerate(cdn_images):
        print(f"\nImage {i+1}:")
        print(f"  src: {img['src']}")
        print(f"  data-src: {img['data-src']}")
        print(f"  alt: {img['alt']}")
        print(f"  class: {img['class']}")
        print(f"  id: {img['id']}")
    
    # Look for Angular components
    print("\n=== Looking for Angular Components ===")
    
    # Common Angular component selectors
    angular_selectors = [
        'app-root', 'app-comic', 'app-story', 'comic-viewer',
        'story-viewer', 'image-gallery', 'comic-strip'
    ]
    
    for selector in angular_selectors:
        elements = scraper.driver.find_elements(By.TAG_NAME, selector)
        if elements:
            print(f"Found {len(elements)} <{selector}> element(s)")
    
    # Check for any elements with ng- attributes
    elements_with_ng = scraper.driver.find_elements(By.XPATH, "//*[@*[starts-with(name(), 'ng-')]]")
    print(f"\nFound {len(elements_with_ng)} elements with ng- attributes")
    
    # Also test ADHDinos
    print("\n\n=== Testing ADHDinos ===")
    test_url2 = "https://tinyview.com/adhdinos/2025/01/15/cartoon"
    print(f"Loading: {test_url2}")
    scraper.driver.get(test_url2)
    time.sleep(5)
    
    # Save ADHDinos HTML
    html_file2 = os.path.join(debug_dir, "adhdinos_page.html")
    with open(html_file2, 'w', encoding='utf-8') as f:
        f.write(scraper.driver.page_source)
    print(f"Saved HTML to: {html_file2}")
    
    scraper.close_driver()
    print(f"\nDebug files saved to: {debug_dir}/")
    print("You can now examine the HTML files to understand the structure better.")


if __name__ == "__main__":
    debug_tinyview()