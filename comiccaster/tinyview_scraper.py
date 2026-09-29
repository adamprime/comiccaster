"""
Tinyview comic scraper: fetches a strip's page from the address it was listed
under and extracts that strip's own panel images from the Tinyview CDN, for both
single- and multi-image comics.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from .tinyview_strips import canonical_strip_url, image_belongs_to_strip
from .webdriver_setup import build_chrome_driver

logger = logging.getLogger(__name__)


def _unproxied(src: str) -> str:
    """Return the CDN address behind a Next.js image-proxy ``src``, else ``src`` itself.

    Format: /_next/image?url=https%3A%2F%2Fcdn.tinyview.com%2F...&w=1080&q=100
    """
    if '/_next/image?url=' in src:
        try:
            query_params = parse_qs(urlparse(src).query)
            if 'url' in query_params:
                return unquote(query_params['url'][0])
        except Exception:
            pass
    return src


def _own_panel_url(src: str, strip_url: str) -> Optional[str]:
    """Return the panel address ``src`` shows when it is one of ``strip_url``'s own panels.

    A strip page also shows panels of other strips filed under the same date, so an
    image counts only when it sits under the strip's own CDN folder, whether the
    page serves it directly or through the image proxy. Banner, profile and
    external-link images are page furniture, not panels.
    """
    url = _unproxied(src)
    try:
        if not image_belongs_to_strip(url, strip_url):
            return None
    except ValueError:  # malformed address, e.g. a broken IPv6 host
        return None
    path = urlparse(url).path
    if '/banner.jpg' in path or 'profile' in path.strip('/').split('/') or 'external-link' in path:
        logger.debug(f"Skipping non-panel image: {src}")
        return None
    return url


class TinyviewScraper(BaseScraper):
    """Handles scraping individual comic pages from Tinyview."""
    
    def __init__(self, max_retries: int = 3):
        """Initialize the TinyviewScraper.
        
        Args:
            max_retries: Maximum number of retries for failed requests
        """
        super().__init__(base_url="https://tinyview.com")
        self.driver = None
        self.max_retries = max_retries
    
    def get_source_name(self) -> str:
        """Return the source name for this scraper."""
        return "tinyview"
    
    def setup_driver(self):
        """Set up the Selenium WebDriver with Chrome or Firefox in headless mode."""
        if not self.driver:
            # Prefer Chrome (more reliable in CI environments); fall back to Firefox.
            try:
                logger.info("Attempting to set up Chrome WebDriver...")
                chrome_options = Options()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-plugins')
                chrome_options.add_argument('--disable-images')
                chrome_options.add_argument('--disable-web-security')
                chrome_options.add_argument('--allow-running-insecure-content')
                chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                self.driver = build_chrome_driver(chrome_options)
                self.driver.set_window_size(1920, 1080)
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(30)
                logger.info("Chrome WebDriver set up successfully")
                return
                
            except Exception as chrome_error:
                logger.warning(f"Chrome WebDriver failed: {chrome_error}")
                logger.info("Falling back to Firefox WebDriver...")
            
            # Fallback to Firefox if Chrome fails
            try:
                firefox_options = FirefoxOptions()
                firefox_options.add_argument('--headless')
                firefox_options.add_argument('--no-sandbox')
                firefox_options.add_argument('--disable-dev-shm-usage')
                firefox_options.add_argument('--disable-gpu')
                firefox_options.add_argument('--disable-extensions')
                firefox_options.add_argument('--disable-plugins')
                firefox_options.add_argument('--disable-images')
                firefox_options.set_preference("general.useragent.override", 
                    "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0")
                
                # Try to find Firefox binary in common locations
                firefox_paths = [
                    '/usr/bin/firefox',  # Standard apt install
                    '/snap/bin/firefox',  # Snap install
                    'firefox'  # Let system find it
                ]
                
                firefox_binary = None
                for path in firefox_paths:
                    try:
                        import subprocess
                        import os.path
                        if os.path.isfile(path) and os.access(path, os.X_OK):
                            result = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=10)
                            if result.returncode == 0:
                                firefox_binary = path
                                logger.info(f"Found Firefox at: {path}")
                                break
                    except Exception as e:
                        logger.debug(f"Could not verify Firefox at {path}: {e}")
                        continue
                
                # Set binary location if we found a specific path
                if firefox_binary and firefox_binary != 'firefox':
                    firefox_options.binary_location = firefox_binary
                    logger.info(f"Setting Firefox binary location to: {firefox_binary}")
                
                self.driver = webdriver.Firefox(options=firefox_options)
                self.driver.set_window_size(1920, 1080)
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(30)
                logger.info("Firefox WebDriver set up successfully")
                
            except Exception as firefox_error:
                logger.error(f"Firefox WebDriver also failed: {firefox_error}")
                raise Exception(f"Both Chrome and Firefox WebDriver initialization failed. Chrome: {chrome_error}, Firefox: {firefox_error}")
    
    def close_driver(self):
        """Close the Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def get_recent_comics(self, comic_slug: str, days_back: int = 90) -> List[Dict[str, str]]:
        """
        Get all recent comics from the last N days by parsing the comic's main page.
        
        Args:
            comic_slug (str): The slug of the comic to fetch (e.g., 'nick-anderson', 'adhdinos').
            days_back (int): Number of days to look back for recent comics.
            
        Returns:
            List[Dict[str, str]]: List of comic info dictionaries with keys: href, date, title
        """
        comic_main_url = f"{self.base_url}/{comic_slug}"
        
        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                self.setup_driver()
                logger.info(f"Fetching comic main page (attempt {attempt + 1}/{self.max_retries}): {comic_main_url}")

                self.driver.get(comic_main_url)

                # Bail out early on 404 / error pages.
                page_title = self.driver.title.lower()
                if '404' in page_title or 'not found' in page_title or 'error' in page_title:
                    logger.warning(f"Comic not found (404) for {comic_main_url}")
                    return []
                
                # Wait for the page to load
                time.sleep(3)

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                all_links = soup.find_all('a', href=True)

                recent_comics = []
                cutoff_date = datetime.now() - timedelta(days=days_back)
                
                for link in all_links:
                    href = link['href']

                    if not href.startswith(f'/{comic_slug}/'):
                        continue

                    # Extract date from URL path like /lunarbaboon/2025/07/15/wanted
                    try:
                        parsed = urlparse(urljoin(self.base_url, href))
                        path_parts = parsed.path.strip('/').split('/')
                        
                        # Expected format: ['comic-slug', 'YYYY', 'MM', 'DD', 'title']
                        if len(path_parts) >= 4:
                            comic_name = path_parts[0]
                            if comic_name != comic_slug:
                                continue
                                
                            year_str, month_str, day_str = path_parts[1], path_parts[2], path_parts[3]
                            
                            # Parse the date
                            try:
                                comic_date = datetime(int(year_str), int(month_str), int(day_str))
                                
                                # Only include comics from the last N days
                                if comic_date >= cutoff_date:
                                    title = path_parts[4] if len(path_parts) > 4 else "untitled"
                                    recent_comics.append({
                                        'href': href,
                                        'date': comic_date.strftime('%Y/%m/%d'),
                                        'date_obj': comic_date,
                                        'title': title,
                                        'url': urljoin(self.base_url, href)
                                    })
                                    logger.info(f"Found recent comic: {href} from {comic_date.strftime('%Y-%m-%d')}")
                            except ValueError:
                                # Invalid date format, skip
                                continue
                    except Exception:
                        # Skip invalid URLs
                        continue
                
                # Sort by date (newest first) and return
                recent_comics.sort(key=lambda x: x['date_obj'], reverse=True)
                logger.info(f"Found {len(recent_comics)} recent comics for {comic_slug}")
                
                return recent_comics
                
            except TimeoutException as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} for {comic_main_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff: wait 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {comic_main_url}")
                    return []
                    
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{self.max_retries} for {comic_main_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {comic_main_url}")
                    return []
        
        return []

    def _count_own_panels(self, strip_url: str) -> int:
        """Count the images on the open page that are ``strip_url``'s own panels."""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        return sum(1 for img in soup.find_all('img') if _own_panel_url(img.get('src', ''), strip_url))

    def fetch_comic_page(self, comic_slug: str, date: str, *,
                         strip_url: Optional[str] = None) -> Optional[tuple]:
        """
        Fetch one strip's page using Selenium with retry logic and error handling.

        Args:
            comic_slug (str): The slug of the comic to fetch (e.g., 'nick-anderson', 'adhdinos').
            date (str): The date in YYYY/MM/DD format.
            strip_url (str): The address the strip was listed under. That page is loaded
                directly. Without it, the series listing is searched for the first strip
                filed under ``date``. Keyword-only, so the title slug older callers pass
                third can never become an address.

        Returns:
            Optional[tuple]: A tuple of (html_content, strip_url), where strip_url is the
            address loaded, or None if fetching fails.
        """
        if strip_url is None:
            # Only the date is known: take the first strip the listing files under it.
            target_comic = next(
                (comic for comic in self.get_recent_comics(comic_slug) if comic['date'] == date),
                None,
            )
            if not target_comic:
                logger.warning(f"No comic found for {comic_slug} on {date}")
                return None
            strip_url = target_comic['url']

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                if not self.driver:
                    self.setup_driver()
                    
                logger.info(f"Fetching comic strip (attempt {attempt + 1}/{self.max_retries}): {strip_url}")
                
                self.driver.get(strip_url)
                
                # Wait for the strip page to load initially
                time.sleep(2)
                
                # Wait for the strip's own panels, which load via JavaScript. Sibling
                # strips' panels on the same page must not end the wait early.
                try:
                    # Wait up to 5 seconds for the first panel to appear.
                    WebDriverWait(self.driver, 5).until(
                        lambda _driver: self._count_own_panels(strip_url) > 0
                    )

                    # Some comics load panels progressively; wait until the
                    # panel count stops growing.
                    previous_count = 0
                    stable_count = 0
                    max_wait_iterations = 10  # Max 10 seconds additional wait

                    for _ in range(max_wait_iterations):
                        current_count = self._count_own_panels(strip_url)

                        if current_count == previous_count:
                            stable_count += 1
                            # Stable for 2 iterations means loading is done.
                            if stable_count >= 2:
                                logger.debug(f"Image count stable at {current_count} for {strip_url}")
                                break
                        else:
                            stable_count = 0
                            logger.debug(f"Found {current_count} images (was {previous_count}) for {strip_url}")
                        
                        previous_count = current_count
                        time.sleep(1)
                    
                except Exception:
                    # If wait fails, continue anyway - some comics might not have dynamic loading
                    logger.debug(f"Dynamic content wait timed out for {strip_url}")
                
                return (self.driver.page_source, strip_url)
                
            except TimeoutException as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} for {strip_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff: wait 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {strip_url}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{self.max_retries} for {strip_url}: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Close and reopen driver for clean retry
                    self.close_driver()
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {strip_url}")
                    return None
        
        # This should never be reached, but just in case
        return None
    
    def extract_images(self, html_content: str, comic_slug: str, date: str, *,
                       strip_url: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Extract the strip's own panel images from its page.

        Args:
            html_content (str): The HTML content of the strip's page.
            comic_slug (str): The comic slug (unused; kept for the BaseScraper interface).
            date (str): The date in YYYY/MM/DD format (unused; kept for the BaseScraper interface).
            strip_url (str): The strip's address. Only images under its own CDN folder
                are kept (see comiccaster.tinyview_strips). Without it no image can be
                attributed to a strip, and nothing is returned.

        Returns:
            List[Dict[str, str]]: List of dictionaries containing image data, in page order.
        """
        if not strip_url:
            logger.warning(f"No strip address for {comic_slug} on {date}; no image can be attributed")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        seen_urls = set()  # Track unique images to avoid duplicates
        all_imgs = soup.find_all('img')

        def collect(attribute: str, label: str) -> None:
            for img in all_imgs:
                panel_url = _own_panel_url(img.get(attribute, ''), strip_url)
                if not panel_url:
                    continue
                if panel_url in seen_urls:
                    logger.debug(f"Skipping duplicate image{label}: {panel_url}")
                    continue
                seen_urls.add(panel_url)
                images.append({
                    'url': panel_url,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
                logger.info(f"Found comic image{label} for {strip_url}: {panel_url}")

        collect('src', '')
        # Fallback: lazy-loading pages keep a panel's address in data-src until it
        # scrolls into view. The same own-folder rule applies.
        if not images:
            collect('data-src', ' (data-src)')

        return images
    
    def extract_metadata(self, html_content: str, comic_slug: str, date: str) -> Dict[str, any]:
        """
        Extract metadata from the comic page.
        
        Args:
            html_content (str): The HTML content of the comic page.
            comic_slug (str): The comic slug.
            date (str): The date string.
            
        Returns:
            Dict[str, any]: Dictionary containing metadata.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        metadata = {
            'comic_slug': comic_slug,
            'date': date,
            'title': '',
            'description': ''
        }
        
        # Try to extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.text.strip()
        
        # Try to extract from meta tags
        og_title = soup.find('meta', property='og:title')
        if og_title:
            metadata['title'] = og_title.get('content', metadata['title'])
        
        og_description = soup.find('meta', property='og:description')
        if og_description:
            metadata['description'] = og_description.get('content', '')
        
        # The comic description lives in a <p class="comments"> paragraph. There may
        # be several; skip the "Beat the algorithm" CTA box and take the first real one.
        comments_paragraphs = soup.find_all('p', class_='comments')
        for comments_p in comments_paragraphs:
            description_text = comments_p.get_text(strip=True)
            if description_text and 'Beat the algorithm' not in description_text:
                metadata['description'] = description_text
                logger.info(f"Found comic description: {description_text[:100]}...")
                break
        
        # Parse date
        try:
            date_parts = date.split('/')
            if len(date_parts) == 3:
                metadata['published_date'] = datetime(
                    int(date_parts[0]), 
                    int(date_parts[1]), 
                    int(date_parts[2])
                )
        except:
            logger.warning(f"Could not parse date: {date}")
        
        return metadata
    
    def scrape_comic(self, comic_slug: str, date: str, *,
                     strip_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Main method to scrape a strip's page and extract its own images and metadata.
        
        Args:
            comic_slug (str): The slug of the comic to scrape.
            date (str): The date in YYYY/MM/DD format.
            strip_url (str): The address the strip was listed under; see fetch_comic_page.
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing the comic data, with the strip's
            canonical address as 'url', or None if scraping fails or the page shows none of
            the strip's own panels (so the next run retries it).
        """
        try:
            if not comic_slug or not date:
                logger.error(f"Invalid parameters: comic_slug='{comic_slug}', date='{date}'")
                return None

            fetch_result = self.fetch_comic_page(comic_slug, date, strip_url=strip_url)
            if not fetch_result:
                logger.warning(f"No HTML content retrieved for {comic_slug} on {date}")
                return None
            
            # The address loaded: the one given, or the date lookup's find.
            html_content, strip_url = fetch_result
            
            images = self.extract_images(html_content, comic_slug, date, strip_url=strip_url)
            if not images:
                logger.warning(f"No images under the strip's own folder for {strip_url}; not recording it")
                return None

            metadata = self.extract_metadata(html_content, comic_slug, date)

            result = {
                'source': self.get_source_name(),
                'comic_slug': comic_slug,
                'date': date,
                'title': metadata.get('title', f'{comic_slug} - {date}'),
                'url': canonical_strip_url(strip_url),
                'images': images,
                'image_count': len(images),
                'published_date': metadata.get('published_date', datetime.now()),
                'description': metadata.get('description', '')
            }
            
            # Add convenience fields for single-image comics
            if len(images) == 1:
                result['image_url'] = images[0]['url']
                result['image_alt'] = images[0].get('alt', '')
            
            logger.info(f"Successfully scraped {comic_slug} for {date}: {len(images)} images found")
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error scraping {comic_slug} for {date}: {e}")
            return None
        finally:
            # Ensure driver cleanup happens
            if hasattr(self, '_cleanup_needed'):
                self.close_driver()
    
    def __del__(self):
        """Ensure driver is closed when object is destroyed."""
        self.close_driver()


def main():
    """Main function to demonstrate the TinyviewScraper usage."""
    scraper = TinyviewScraper()
    
    try:
        # Test 1: Nick Anderson (single image comic)
        print("\n=== Testing Nick Anderson (single image) ===")
        today = datetime.now()
        date_str = today.strftime("%Y/%m/%d")
        
        # Try to get today's comic, or a recent one
        result = scraper.scrape_comic('nick-anderson', '2025/01/17')
        if result:
            print(f"\nSuccessfully scraped Nick Anderson comic:")
            print(f"Title: {result.get('title')}")
            print(f"Date: {result.get('date')}")
            print(f"URL: {result.get('url')}")
            print(f"Image count: {result.get('image_count')}")
            if result.get('image_url'):
                print(f"Image URL: {result.get('image_url')}")
        else:
            print("Failed to scrape Nick Anderson comic")
        
        # Test 2: ADHDinos (potentially multiple images)
        print("\n=== Testing ADHDinos (multiple images) ===")
        result = scraper.scrape_comic('adhdinos', '2025/01/15')
        if result:
            print(f"\nSuccessfully scraped ADHDinos comic:")
            print(f"Title: {result.get('title')}")
            print(f"Date: {result.get('date')}")
            print(f"URL: {result.get('url')}")
            print(f"Image count: {result.get('image_count')}")
            for i, img in enumerate(result.get('images', [])):
                print(f"Image {i+1}: {img['url']}")
        else:
            print("Failed to scrape ADHDinos comic")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        scraper.close_driver()


if __name__ == "__main__":
    main()