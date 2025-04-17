#!/usr/bin/env python3
"""Test script for debugging comic scraping and feed generation."""

import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import pytz
from comiccaster.feed_generator import ComicFeedGenerator

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_headers():
    """Get browser-like headers for HTTP requests."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

def verify_image_url(url):
    """Verify that an image URL is accessible."""
    try:
        response = requests.head(url, headers=get_headers(), allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type.lower():
                return True, f"✅ Accessible ({content_type})"
        return False, f"❌ Not accessible (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def scrape_comic(url):
    """Scrape a comic page and print detailed debug information."""
    try:
        logger.info(f"Fetching URL: {url}")
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Print all image elements for debugging
        logger.info("\nFound image elements:")
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src:
                continue
                
            # Skip social media icons
            if any(x in src.lower() for x in ['facebook', 'twitter', 'instagram', 'pinterest', 'icon']):
                continue
                
            # Check if URL is accessible
            accessible, status = verify_image_url(src)
            
            logger.info(f"\nImage URL: {src}")
            logger.info(f"Status: {status}")
            logger.info(f"Class: {img.get('class', [])}")
            logger.info(f"Alt: {img.get('alt', '')}")
            if img.has_attr('data-srcset'):
                logger.info(f"data-srcset: {img['data-srcset']}")
                # Also verify srcset URLs
                for srcset_url in [url.split()[0] for url in img['data-srcset'].split(',')]:
                    accessible, status = verify_image_url(srcset_url)
                    logger.info(f"srcset URL: {srcset_url}")
                    logger.info(f"srcset Status: {status}")
        
        # Print meta tags
        logger.info("\nMeta tags:")
        for meta in soup.find_all('meta'):
            if meta.get('property') in ['og:image', 'twitter:image']:
                content = meta.get('content', '')
                if content:
                    accessible, status = verify_image_url(content)
                    logger.info(f"\n{meta.get('property')}: {content}")
                    logger.info(f"Status: {status}")
        
    except Exception as e:
        logger.error(f"Error scraping comic: {e}")

def main():
    """Main test function."""
    # Test URL
    url = "https://www.gocomics.com/adamathome/2024/04/10"
    logger.info(f"Testing with URL: {url}")
    scrape_comic(url)

if __name__ == "__main__":
    main() 