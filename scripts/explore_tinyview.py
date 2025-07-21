#!/usr/bin/env python3
"""
Explore Tinyview to understand the URL structure and find actual comics.
"""

import sys
import time
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_driver():
    """Set up the Selenium WebDriver with Firefox."""
    options = Options()
    # Run with GUI to see what's happening
    # options.add_argument('-headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1920, 1080)
    logger.info("Firefox WebDriver set up successfully")
    return driver


def explore_tinyview():
    """Explore Tinyview to understand structure."""
    driver = setup_driver()
    
    try:
        # First, let's go to the main page
        logger.info("Visiting Tinyview homepage...")
        driver.get("https://tinyview.com")
        time.sleep(3)
        
        # Save screenshot
        driver.save_screenshot("tinyview_homepage.png")
        logger.info("Saved screenshot: tinyview_homepage.png")
        
        # Get all links
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = soup.find_all('a', href=True)
        
        logger.info(f"\nFound {len(links)} links on homepage")
        
        # Look for comic-related links
        comic_links = []
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                if any(word in href.lower() or word in text.lower() for word in ['comic', 'series', 'adhdinos', 'nick-anderson', 'cartoon']):
                    comic_links.append((href, text))
                    logger.info(f"Potential comic link: {text} -> {href}")
        
        # Try some common patterns
        test_urls = [
            "https://tinyview.com/adhdinos",
            "https://tinyview.com/comics/adhdinos",
            "https://tinyview.com/series/adhdinos",
            "https://tinyview.com/adhdinos/2025/01/17",
            "https://tinyview.com/adhdinos/2025/01/17/cartoon",
            "https://tinyview.com/nick-anderson",
            "https://tinyview.com/comics",
            "https://tinyview.com/directory",
            "https://tinyview.com/browse"
        ]
        
        logger.info("\n\nTesting various URL patterns...")
        for url in test_urls:
            logger.info(f"\nTrying: {url}")
            driver.get(url)
            time.sleep(2)
            
            # Check title
            title = driver.title
            logger.info(f"Page title: {title}")
            
            # Check for 404
            if '404' in title.lower() or 'not found' in title.lower():
                logger.info("❌ 404 - Page not found")
                continue
            
            # Look for images
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Look for comic images
            all_images = soup.find_all('img')
            cdn_images = [img for img in all_images if img.get('src', '').startswith('https://cdn.tinyview.com')]
            
            logger.info(f"Total images: {len(all_images)}")
            logger.info(f"CDN images: {len(cdn_images)}")
            
            if cdn_images:
                for img in cdn_images[:3]:  # Show first 3
                    src = img.get('src', '')
                    alt = img.get('alt', 'no-alt')
                    logger.info(f"  - {alt}: {src}")
            
            # Save screenshot
            screenshot_name = url.replace('https://tinyview.com/', '').replace('/', '_') + '.png'
            driver.save_screenshot(screenshot_name)
            logger.info(f"Saved screenshot: {screenshot_name}")
        
        # Wait for user to explore manually
        input("\n\nPress Enter when you're done exploring manually...")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()


if __name__ == "__main__":
    explore_tinyview()