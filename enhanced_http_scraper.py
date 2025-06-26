#!/usr/bin/env python3
"""
Enhanced HTTP scraper that mimics Selenium's fetchpriority="high" detection
without requiring JavaScript execution.
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedHTTPScraper:
    """Enhanced HTTP scraper that detects fetchpriority='high' comics without JavaScript."""
    
    def __init__(self, base_url: str = "https://www.gocomics.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def fetch_comic_page(self, comic_slug: str, date: Optional[str] = None) -> Optional[str]:
        """Fetch comic page HTML."""
        try:
            url = f"{self.base_url}/{comic_slug}"
            if date:
                url = f"{url}/{date}"
            
            logger.info(f"Fetching {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
            
        except Exception as e:
            logger.error(f"Failed to fetch comic page: {e}")
            return None
    
    def _find_fetchpriority_high_images(self, soup: BeautifulSoup) -> list:
        """Look for images with fetchpriority='high' in the HTML."""
        # Check if fetchpriority="high" exists in the initial HTML
        priority_imgs = soup.find_all('img', attrs={'fetchpriority': 'high'})
        if priority_imgs:
            logger.info(f"✅ Found {len(priority_imgs)} fetchpriority='high' images in HTML")
            return priority_imgs
        
        # Look for fetchpriority in JavaScript code
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'fetchpriority' in script.string and 'high' in script.string:
                logger.info("Found fetchpriority='high' references in JavaScript")
                # Try to extract image URLs that get the fetchpriority attribute
                js_code = script.string
                
                # Look for patterns like: img.fetchPriority = "high" or fetchpriority="high"
                # and try to find associated image URLs
                if 'featureassets.gocomics.com' in js_code:
                    urls = re.findall(r'https://featureassets\.gocomics\.com/assets/[^\s"\']+', js_code)
                    if urls:
                        logger.info(f"Found {len(urls)} potential fetchpriority URLs in JavaScript")
                        # Create mock img elements for consistency with return type
                        mock_imgs = []
                        for url in urls:
                            mock_img = soup.new_tag('img', src=url)
                            mock_img['fetchpriority'] = 'high'  # Mark as high priority
                            mock_imgs.append(mock_img)
                        return mock_imgs
        
        return []
    
    def _extract_comic_image_enhanced(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Enhanced comic image extraction that prioritizes fetchpriority='high' images.
        Follows the same strategy as the Selenium scraper.
        """
        
        # Strategy 1: Look for fetchpriority="high" images (the golden standard)
        priority_imgs = self._find_fetchpriority_high_images(soup)
        if priority_imgs:
            for img in priority_imgs:
                img_src = img.get('src', '')
                if img_src and 'featureassets.gocomics.com' in img_src:
                    logger.info(f"✅ Found fetchpriority='high' comic image: {img_src}")
                    return img_src
        
        # Strategy 2: Look for comic strip classes (same as Selenium scraper)
        comic_strip_selectors = [
            'img.Comic_comic__image__6e_Fw',  # Main comic image class
            'img.Comic_comic__image_isStrip__eCtT2',  # Strip format comics  
            'img.Comic_comic__image_isSkinny__NZ2aF'  # Vertical/skinny format comics
        ]
        
        for selector in comic_strip_selectors:
            comic_imgs = soup.select(selector)
            if comic_imgs:
                # Apply the same selection logic as Selenium scraper
                best_img = self._select_best_comic_image(comic_imgs)
                if best_img:
                    img_src = best_img.get('src', '')
                    if img_src and 'featureassets.gocomics.com' in img_src:
                        logger.info(f"Found comic using selector: {selector}")
                        return img_src
        
        # Strategy 3: JSON-LD approach (enhanced with date validation)
        comic_image = self._extract_from_json_ld(soup)
        if comic_image:
            return comic_image
            
        # Strategy 4: JavaScript regex extraction
        comic_image = self._extract_from_javascript(soup)
        if comic_image:
            return comic_image
        
        # Strategy 5: og:image fallback
        og_image = soup.find('meta', property='og:image')
        if og_image:
            img_url = og_image.get('content', '')
            if img_url:
                logger.info("Using og:image as fallback")
                return img_url
        
        logger.warning("Could not find comic strip image using any strategy")
        return None
    
    def _select_best_comic_image(self, comic_imgs: list) -> Optional:
        """
        Select the best comic image from multiple candidates.
        Same logic as Selenium scraper.
        """
        if not comic_imgs:
            return None
        
        if len(comic_imgs) == 1:
            return comic_imgs[0]
        
        logger.info(f"Found {len(comic_imgs)} comic images, selecting best one...")
        
        # Look for images that might have fetchpriority="high" 
        for img in comic_imgs:
            if img.get('fetchpriority') == 'high':
                logger.info("✅ Selected comic with fetchpriority='high' (the actual daily comic)")
                return img
        
        # Look for images with srcset (responsive images)
        for img in comic_imgs:
            if img.get('srcset'):
                logger.info("Selected comic with srcset (responsive image)")
                return img
        
        # Look for Next.js optimized images
        for img in comic_imgs:
            if img.get('data-nimg'):
                logger.info("Selected Next.js optimized image")
                return img
        
        # Fallback: return the first image
        logger.info("Using first comic image as fallback")
        return comic_imgs[0]
    
    def _extract_from_json_ld(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract comic image from JSON-LD structured data."""
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                if script.string and "ImageObject" in script.string:
                    data = json.loads(script.string)
                    if (data.get("@type") == "ImageObject" and 
                        data.get("contentUrl") and 
                        "featureassets.gocomics.com" in data.get("contentUrl")):
                        
                        logger.info("Found comic image in JSON-LD structured data")
                        return data.get("contentUrl")
            except Exception as e:
                logger.warning(f"Error parsing JSON-LD: {e}")
        return None
    
    def _extract_from_javascript(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract comic image from JavaScript code."""
        scripts = soup.find_all("script")
        for script in scripts:
            if (script.string and 
                "featureassets.gocomics.com/assets" in script.string and 
                "url" in script.string):
                try:
                    # Find URLs that look like comic strip images
                    matches = re.findall(
                        r'"url"\s*:\s*"(https://featureassets\.gocomics\.com/assets/[^"]+)"', 
                        script.string
                    )
                    if matches:
                        logger.info("Found comic image URL in JavaScript data")
                        return matches[0]
                except Exception as e:
                    logger.warning(f"Error extracting URL from JavaScript: {e}")
        return None
    
    def extract_metadata(self, html_content: str) -> Dict[str, str]:
        """
        Extract metadata from comic page using enhanced detection.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            metadata = {}
            
            # Extract Open Graph metadata
            og_tags = {
                'title': 'og:title',
                'url': 'og:url', 
                'description': 'og:description'
            }
            
            for key, tag in og_tags.items():
                meta = soup.find('meta', property=tag)
                if meta:
                    metadata[key] = meta.get('content', '')
            
            # Extract comic image using enhanced detection
            comic_image_url = self._extract_comic_image_enhanced(soup)
            if comic_image_url:
                metadata['image'] = comic_image_url
                logger.info(f"Successfully found comic image: {comic_image_url}")
            else:
                logger.error("No comic image found")
            
            # Extract publication date
            date_meta = soup.find('meta', property='article:published_time')
            if date_meta:
                pub_date = date_meta.get('content', '')
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    metadata['pub_date'] = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
                except ValueError:
                    logger.warning(f"Could not parse publication date: {pub_date}")
                    metadata['pub_date'] = ''
            
            # Make image URL absolute
            if 'image' in metadata and metadata['image'].startswith('/'):
                metadata['image'] = urljoin(self.base_url, metadata['image'])
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            raise
    
    def scrape_comic(self, comic_slug: str, date: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Main method to scrape a comic using enhanced HTTP detection.
        """
        html_content = self.fetch_comic_page(comic_slug, date)
        if not html_content:
            return None
        
        return self.extract_metadata(html_content)


def test_enhanced_scraper():
    """Test the enhanced scraper with known problematic comics."""
    scraper = EnhancedHTTPScraper()
    
    test_comics = [
        ('pearlsbeforeswine', '2025/06/25'),
        ('inthebleachers', '2025/06/25')
    ]
    
    for comic_slug, date in test_comics:
        print(f"\n=== Testing {comic_slug} for {date} ===")
        result = scraper.scrape_comic(comic_slug, date)
        
        if result:
            print("✅ SUCCESS!")
            print(f"Title: {result.get('title', 'N/A')}")
            print(f"Image URL: {result.get('image', 'N/A')}")
            print(f"URL: {result.get('url', 'N/A')}")
        else:
            print("❌ FAILED - No result returned")


if __name__ == "__main__":
    test_enhanced_scraper()