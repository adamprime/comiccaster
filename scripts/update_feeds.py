#!/usr/bin/env python3
"""
Update script for ComicCaster feeds
Runs daily to update all comic feeds with the latest content
"""

import json
import os
import logging
import sys
from datetime import datetime, timedelta, timezone
import pytz
import requests
from bs4 import BeautifulSoup
from comiccaster.feed_generator import ComicFeedGenerator
from feedgen.entry import FeedEntry
import feedparser
import configparser
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml
from dateutil import parser as date_parser
import concurrent.futures
from functools import partial
from email.utils import parsedate_to_datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set timezone to US/Eastern (GoComics timezone)
TIMEZONE = pytz.timezone('US/Eastern')

# GoComics base URL
COMICS_URL = "https://www.gocomics.com"

# Constants for concurrent processing
MAX_WORKERS = 8  # Maximum number of concurrent workers (increased back up with HTTP-only approach)
REQUEST_TIMEOUT = 10  # Timeout for HTTP requests in seconds
MAX_RETRIES = 3  # Maximum number of retries for failed requests

# Define the path relative to the script's location
SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
FEEDS_OUTPUT_DIR = WORKSPACE_ROOT / "public" / "feeds" # Output to public/feeds

# Add the parent directory to sys.path to find the comiccaster module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from comiccaster.feed_generator import ComicFeedGenerator

def load_comics_list():
    """Load the list of comics from comics_list.json."""
    try:
        with open('comics_list.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading comics list: {e}")
        sys.exit(1)

# Removed get_headers() function - no longer needed since we use ComicScraper with Selenium

def scrape_comic(comic, date_str):
    """Scrape a comic from GoComics for a given date using enhanced HTTP detection."""
    logging.info(f"Fetching {comic['name']} for {date_str}")
    
    try:
        # Convert date format if needed
        if '/' in date_str:
            # Input is YYYY/MM/DD (already correct)
            target_date = datetime.strptime(date_str, '%Y/%m/%d').date()
            scraper_date_str = date_str
        else:
            # Convert YYYY-MM-DD to YYYY/MM/DD for scraper
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            scraper_date_str = target_date.strftime('%Y/%m/%d')
        
        # Use enhanced HTTP scraping (mimics Selenium logic without browser)
        metadata = scrape_comic_enhanced_http(comic['slug'], scraper_date_str)
        
        if metadata:
            # Convert to format expected by feed updater
            return {
                'title': f"{comic['name']} - {target_date.strftime('%Y-%m-%d')}",
                'url': metadata.get('url', f"https://www.gocomics.com/{comic['slug']}/{scraper_date_str}"),
                'image': metadata.get('image', ''),
                'pub_date': target_date.strftime('%Y-%m-%d'),
                'description': metadata.get('description', f'Comic strip for {target_date.strftime("%Y-%m-%d")}'),
                'id': metadata.get('url', f"https://www.gocomics.com/{comic['slug']}/{scraper_date_str}")
            }
        else:
            logging.error(f"Enhanced HTTP scraper returned no metadata for {comic['name']} on {date_str}")
            return None
            
    except Exception as e:
        logging.error(f"Error using enhanced HTTP scraper for {comic['name']} on {date_str}: {e}")
        return None


def scrape_comic_enhanced_http(comic_slug: str, date_str: str) -> Optional[Dict[str, str]]:
    """Enhanced HTTP scraping that mimics Selenium's detection strategies."""
    try:
        url = f"https://www.gocomics.com/{comic_slug}/{date_str}"
        response = requests.get(url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strategy 1: JSON-LD structured data with DATE MATCHING (the key!)
        # This mimics what fetchpriority="high" does - finds the comic for the specific date
        # This is the MOST RELIABLE approach for getting actual daily comics vs "best of"
        target_date = datetime.strptime(date_str, '%Y/%m/%d')
        # Format as "June 25, 2025" (remove leading zero from day)
        target_date_formatted = target_date.strftime('%B %d, %Y').replace(' 0', ' ')  # Remove leading zero from day
        
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                if script.string and "ImageObject" in script.string:
                    data = json.loads(script.string)
                    if (data.get("@type") == "ImageObject" and 
                        data.get("contentUrl") and 
                        "featureassets.gocomics.com" in data.get("contentUrl")):
                        
                        # CHECK IF THE NAME MATCHES OUR TARGET DATE
                        name = data.get("name", "")
                        if target_date_formatted in name:
                            logging.info(f"✅ Found JSON-LD comic for exact date: {target_date_formatted}")
                            return {
                                'image': data.get("contentUrl"),
                                'url': url,
                                'title': soup.find('title').get_text() if soup.find('title') else '',
                                'description': f'Comic strip for {date_str}'
                            }
                        else:
                            logging.debug(f"JSON-LD name '{name}' doesn't match target date '{target_date_formatted}'")
                            
            except Exception as e:
                logging.warning(f"Error parsing JSON-LD: {e}")
        
        logging.warning(f"No JSON-LD entry found matching date: {target_date_formatted}")
        
        # Strategy 2: Look for comic strip classes (fallback)
        comic_strip_selectors = [
            'img.Comic_comic__image__6e_Fw',  # Main comic image class
            'img.Comic_comic__image_isStrip__eCtT2',  # Strip format comics  
            'img.Comic_comic__image_isSkinny__NZ2aF'  # Vertical/skinny format comics
        ]
        
        for selector in comic_strip_selectors:
            comic_imgs = soup.select(selector)
            if comic_imgs:
                # Apply enhanced selection logic
                best_img = select_best_comic_image_http(comic_imgs)
                if best_img:
                    img_src = best_img.get('src', '')
                    if img_src and 'featureassets.gocomics.com' in img_src:
                        logging.info(f"Found comic using selector: {selector}")
                        return {
                            'image': img_src,
                            'url': url,
                            'title': soup.find('title').get_text() if soup.find('title') else '',
                            'description': f'Comic strip for {date_str}'
                        }
        
        # Strategy 3: JavaScript regex extraction
        scripts = soup.find_all("script")
        for script in scripts:
            if (script.string and 
                "featureassets.gocomics.com/assets" in script.string and 
                "url" in script.string):
                try:
                    matches = re.findall(
                        r'"url"\s*:\s*"(https://featureassets\.gocomics\.com/assets/[^"]+)"', 
                        script.string
                    )
                    if matches:
                        logging.info("Found comic image URL in JavaScript data")
                        return {
                            'image': matches[0],
                            'url': url,
                            'title': soup.find('title').get_text() if soup.find('title') else '',
                            'description': f'Comic strip for {date_str}'
                        }
                except Exception as e:
                    logging.warning(f"Error extracting URL from JavaScript: {e}")
        
        # Strategy 4: og:image fallback
        og_image = soup.find('meta', property='og:image')
        if og_image:
            img_url = og_image.get('content', '')
            if img_url:
                logging.info("Using og:image as fallback")
                return {
                    'image': img_url,
                    'url': url,
                    'title': soup.find('title').get_text() if soup.find('title') else '',
                    'description': f'Comic strip for {date_str}'
                }
        
        logging.error(f"No comic image found for {url}")
        return None
        
    except Exception as e:
        logging.error(f"Error in enhanced HTTP scraping: {e}")
        return None


def select_best_comic_image_http(comic_imgs: list) -> Optional:
    """Select the best comic image from multiple candidates (HTTP version)."""
    if not comic_imgs:
        return None
    
    if len(comic_imgs) == 1:
        return comic_imgs[0]
    
    logging.info(f"Found {len(comic_imgs)} comic images, selecting best one...")
    
    # Look for images with srcset (responsive images - good indicator)
    for img in comic_imgs:
        if img.get('srcset'):
            logging.info("Selected comic with srcset (responsive image)")
            return img
    
    # Look for Next.js optimized images
    for img in comic_imgs:
        if img.get('data-nimg'):
            logging.info("Selected Next.js optimized image")
            return img
    
    # Fallback: return the first image
    logging.info("Using first comic image as fallback")
    return comic_imgs[0]


def get_headers():
    """Get browser-like headers for HTTP requests."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

def process_comic_date(comic_info: Dict[str, str], date: datetime) -> Optional[Dict[str, any]]:
    """
    Processes scraping for a single comic on a specific date.

    Args:
        comic_info: Dictionary containing comic details.
        date: The date for which to scrape the comic.

    Returns:
        A dictionary with scraped comic data or None if scraping fails.
    """
    date_str = date.strftime("%Y/%m/%d")
    comic_url = f"{comic_info['url']}/{date_str}"
    try:
        # Simulate scraping delay
        # time.sleep(random.uniform(0.5, 1.5))
        scrape_result = scrape_comic(comic_info, date_str)
        if scrape_result:
            # Convert the date string from scrape_result to a datetime object for sorting
            # Ensure the date from scrape_result matches the requested date, or handle discrepancies
            scraped_date_str = scrape_result.get("date") # e.g., "April 09, 2025" or "2025-04-09"
            try:
                 # Handle formats like "Month Day, Year" or "YYYY-MM-DD"
                if ',' in scraped_date_str:
                    parsed_date = datetime.strptime(scraped_date_str, "%B %d, %Y")
                else:
                    parsed_date = datetime.strptime(scraped_date_str, "%Y-%m-%d")
                # Make the date timezone-aware (UTC)
                scrape_result['pub_date'] = pytz.UTC.localize(parsed_date)

            except ValueError as e:
                 logger.warning(f"Could not parse date '{scraped_date_str}' for {comic_info['name']} on {date_str}: {e}. Using requested date.")
                 # Fallback to the requested date if parsing fails
                 scrape_result['pub_date'] = date # Already timezone-aware UTC

            # Add comic slug for reference if needed later
            scrape_result['comic_slug'] = comic_info['slug']
            return scrape_result
        else:
            logger.warning(f"No scrape result for {comic_info['name']} on {date_str}")
            return None
    except Exception as e:
        logger.error(f"Error processing {comic_info['name']} for date {date_str}: {e}")
        return None

def load_existing_entries(feed_path):
    """Load existing entries from a feed file."""
    entries = []
    seen_dates = {}  # Track entries by date and use latest version
    try:
        if os.path.exists(feed_path):
            feed = feedparser.parse(feed_path)
            for entry in feed.entries:
                # Extract date from title
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', entry.title)
                if not date_match:
                    continue
                entry_date = date_match.group(0)
                
                # Parse the publication date
                pub_date = None
                if hasattr(entry, 'published'):
                    try:
                        pub_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')
                    except (ValueError, TypeError):
                        # If parsing fails, use current time
                        pub_date = datetime.now(timezone.utc)
                
                # Look for image URL in enclosures first
                image_url = ""
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if enclosure.get('type', '').startswith('image/'):
                            url = enclosure.get('href', '')
                            # Skip social media preview images and staging assets
                            if 'GC_Social_FB' not in url and 'staging-assets' not in url:
                                image_url = url
                                break
                
                # Extract image from description if no enclosure found
                if not image_url and hasattr(entry, 'description'):
                    # Look for img tag in description
                    match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
                    if match:
                        url = match.group(1)
                        # Skip social media preview images and staging assets
                        if 'GC_Social_FB' not in url and 'staging-assets' not in url:
                            image_url = url
                
                # Only add entry if we found a valid image URL
                if image_url:
                    entry_data = {
                        'title': entry.title,
                        'url': entry.link,
                        'image_url': image_url,
                        'description': entry.description,
                        'pub_date': pub_date.strftime('%a, %d %b %Y %H:%M:%S %z') if pub_date else '',
                        'id': entry.get('id', f"{entry.link}#{entry_date}")
                    }
                    
                    # Keep only the latest version of an entry for a given date
                    if entry_date not in seen_dates or pub_date > seen_dates[entry_date]['pub_date']:
                        seen_dates[entry_date] = {
                            'entry': entry_data,
                            'pub_date': pub_date
                        }
    except Exception as e:
        logging.error(f"Error loading existing entries from {feed_path}: {e}")
    
    # Add only the latest version of each entry
    entries = [data['entry'] for data in seen_dates.values()]
    return entries

def regenerate_feed(comic_info: Dict[str, str], new_entries: List[Dict[str, any]]):
    """
    Regenerates the feed file for a comic, merging new entries with existing ones.

    Args:
        comic_info: Dictionary containing comic details.
        new_entries: List of newly scraped comic entry dictionaries. Each should have 'pub_date' (datetime), 'id' or 'url'.
    """
    logger.info(f"Regenerating feed for {comic_info['name']}...")
    generator = ComicFeedGenerator(output_dir=str(FEEDS_OUTPUT_DIR))
    feed_path = FEEDS_OUTPUT_DIR / f"{comic_info['slug']}.xml"

    all_entries = {} # Use dict for deduplication based on unique ID (e.g., URL)

    # 1. Load existing entries from the feed file
    if feed_path.exists():
        try:
            logger.debug(f"Loading existing feed: {feed_path}")
            parsed_feed = feedparser.parse(str(feed_path))
            if parsed_feed.bozo:
                logger.warning(f"Existing feed '{feed_path}' may be ill-formed: {parsed_feed.bozo_exception}")

            for entry in parsed_feed.entries:
                try:
                    # Extract necessary data and ensure timezone-aware date
                    pub_date = datetime.now(pytz.UTC) # Default fallback
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                         # feedparser gives time.struct_time, convert to datetime
                         ts = time.mktime(entry.published_parsed)
                         naive_dt = datetime.fromtimestamp(ts)
                         pub_date = pytz.UTC.localize(naive_dt) # Assume UTC if no timezone
                    elif hasattr(entry, 'published'):
                         # Try parsing the published string
                         try:
                             parsed_dt = parsedate_to_datetime(entry.published)
                             if parsed_dt.tzinfo is None:
                                 pub_date = pytz.UTC.localize(parsed_dt)
                             else:
                                 pub_date = parsed_dt.astimezone(pytz.UTC)
                         except Exception as parse_err:
                             logger.warning(f"Could not parse date string '{entry.published}' for existing entry {entry.get('id', entry.get('link', 'Unknown'))}: {parse_err}. Using default.")

                    # Use entry link or id as a unique key for deduplication
                    # Prefer 'id' if available, otherwise use 'link'
                    entry_id = entry.get('id', entry.get('link'))
                    if not entry_id:
                        logger.warning(f"Skipping existing entry with no id or link.")
                        continue

                    # Store existing entry data in a format similar to new_entries
                    # Ensure all necessary fields for generate_feed are present
                    entry_data = {
                        'title': entry.get('title', ''),
                        'url': entry.get('link', ''), # Link is often the unique URL
                        'id': entry_id,
                        'pub_date': pub_date,
                        'description': entry.get('summary', entry.get('description', '')),
                        # Attempt to extract image_url if structured in description
                        'image_url': extract_image_from_description(entry.get('summary', entry.get('description', ''))),
                    }
                    # Only add if we have a valid ID
                    all_entries[entry_id] = entry_data

                except Exception as e:
                    entry_identifier = entry.get('id', entry.get('link', 'UNKNOWN'))
                    logger.error(f"Error processing existing entry '{entry_identifier}': {e}", exc_info=True)
                    continue # Skip problematic entries

        except Exception as e:
            logger.error(f"Error parsing existing feed file '{feed_path}': {e}", exc_info=True)
            # Continue without existing entries if parsing fails

    # 2. Add new entries, overwriting duplicates based on ID
    logger.debug(f"Adding {len(new_entries)} new entries.")
    for entry_data in new_entries:
        # Use URL or a generated ID as the key for deduplication
        entry_id = entry_data.get('id', entry_data.get('url'))
        if not entry_id:
             # Generate an ID if missing, e.g., based on URL and date
             entry_id = f"{entry_data.get('url', comic_info['url'])}#{entry_data.get('pub_date', datetime.now(pytz.UTC)).isoformat()}"
             entry_data['id'] = entry_id # Ensure ID exists in the data

        # Ensure pub_date is timezone-aware
        if isinstance(entry_data.get('pub_date'), datetime) and entry_data['pub_date'].tzinfo is None:
            entry_data['pub_date'] = pytz.UTC.localize(entry_data['pub_date'])
        elif not isinstance(entry_data.get('pub_date'), datetime):
             logger.warning(f"New entry for {entry_id} missing valid datetime pub_date. Using now().")
             entry_data['pub_date'] = datetime.now(pytz.UTC)


        all_entries[entry_id] = entry_data # Add/overwrite entry

    # 3. Sort all unique entries by publication date (newest first)
    logger.debug(f"Total unique entries before sorting: {len(all_entries)}")
    sorted_entries = sorted(all_entries.values(), key=lambda x: x['pub_date'], reverse=True)
    # Add debug logging to verify sort order
    if sorted_entries:
        logger.debug(f"Sorted entries dates (newest first?): {[entry['pub_date'].strftime('%Y-%m-%d') for entry in sorted_entries[:3]]}")

    # REVERSE the list: If feedgen prepends entries, feeding it oldest-first
    # will result in newest-first output.
    sorted_entries.reverse()
    if sorted_entries:
        logger.debug(f"Reversed sorted entries dates (now oldest first?): {[entry['pub_date'].strftime('%Y-%m-%d') for entry in sorted_entries[:3]]}")

    # Optional: Limit the number of entries in the feed
    max_feed_entries = 100 # Example limit
    if len(sorted_entries) > max_feed_entries:
        logger.info(f"Limiting feed entries from {len(sorted_entries)} to {max_feed_entries}.")
        sorted_entries = sorted_entries[:max_feed_entries]


    # 4. Generate the feed using ComicFeedGenerator
    logger.info(f"Generating final feed with {len(sorted_entries)} entries.")
    success = generator.generate_feed(comic_info, sorted_entries)

    if success:
        logger.info(f"Successfully regenerated feed for {comic_info['name']} at {feed_path}")
    else:
        logger.error(f"Failed to regenerate feed for {comic_info['name']}")

    return success

def extract_image_from_description(description: str) -> Optional[str]:
    """
    Helper function to extract the first <img> src URL from an HTML description string.
    """
    if not description:
        return None
    # Basic regex to find the first <img src="...">
    match = re.search(r'<img[^>]+src="([^"]+)"', description, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def update_feed(comic_info: Dict[str, str], days_to_scrape: int = 10):
    """Update a comic's feed by scraping the last N days and regenerating the feed."""
    logger.info(f"Starting update for {comic_info['name']} - scraping last {days_to_scrape} days.")

    # Ensure the output directory exists (using public/feeds directly)
    output_dir = Path('public/feeds')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get the target dates in chronological order (oldest to newest)
    today = datetime.now(TIMEZONE)
    target_dates = [
        (today - timedelta(days=i)).strftime('%Y/%m/%d')
        for i in range(days_to_scrape - 1, -1, -1)  # e.g., for 10 days: 9 days ago -> today
    ]

    scraped_entries = []
    
    # Use ThreadPoolExecutor for concurrent scraping
    # Note: Using 'with' ensures threads are cleaned up properly
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Map scrape_comic function over the target dates
        # partial allows us to pass the 'comic' argument to scrape_comic
        future_to_date = {
            executor.submit(scrape_comic, comic_info, date_str): date_str 
            for date_str in target_dates
        }

        # Process completed futures as they finish
        for future in concurrent.futures.as_completed(future_to_date):
            date_str = future_to_date[future]
            try:
                # Get the result from the future (the scraped metadata dict or None)
                metadata = future.result()
                if metadata:
                    # Make sure the pub_date is a datetime object for sorting later
                    # The current scrape_comic returns a string 'YYYY-MM-DD'
                    try:
                        # Convert 'YYYY-MM-DD' string to datetime object in UTC
                        metadata['pub_date'] = datetime.strptime(metadata['pub_date'], '%Y-%m-%d').replace(tzinfo=pytz.UTC)
                    except (ValueError, KeyError) as date_err:
                         logger.warning(f"Could not parse pub_date '{metadata.get('pub_date')}' for {comic_info['name']} on {date_str}: {date_err}")
                         # Assign a default date or skip if critical? For now, let's keep it but log warning
                         # Assigning based on the target date might be safer
                         try:
                            parsed_date_from_str = datetime.strptime(date_str, '%Y/%m/%d').replace(tzinfo=pytz.UTC)
                            metadata['pub_date'] = parsed_date_from_str
                            logger.info(f"Assigned pub_date {parsed_date_from_str.strftime('%Y-%m-%d')} based on target date.")
                         except ValueError:
                             logger.error(f"Could not parse target date {date_str} either. Skipping entry.")
                             continue # Skip this entry if we can't determine a reliable date

                    scraped_entries.append(metadata)
                    logger.info(f"Successfully scraped {comic_info['name']} for {date_str}")
                else:
                    # Log if scrape_comic returned None (already logged inside scrape_comic, but good for overview)
                    logger.warning(f"Failed to scrape {comic_info['name']} for {date_str} (returned None)")
            except Exception as exc:
                # Catch any exceptions raised during the future's execution
                logger.error(f"{comic_info['name']} on {date_str} generated an exception: {exc}")

    # Check if we actually got any entries
    if not scraped_entries:
        logger.warning(f"No entries were successfully scraped for {comic_info['name']}. Feed will not be regenerated.")
        return False # Indicate that no update occurred

    # Sort the successfully scraped entries by publication date (newest first for RSS)
    # Ensure pub_date is a datetime object before sorting
    try:
         scraped_entries.sort(key=lambda x: x.get('pub_date', datetime.min.replace(tzinfo=pytz.UTC)), reverse=True)
    except TypeError as sort_err:
        logger.error(f"Error sorting entries for {comic_info['name']} due to inconsistent pub_date types: {sort_err}")
        # Attempt recovery or fail gracefully? For now, log error and proceed with potentially unsorted entries.
        # It might be better to filter out entries with invalid pub_dates here.

    # Call regenerate_feed with ONLY the newly scraped entries
    logger.info(f"Regenerating feed for {comic_info['name']} with {len(scraped_entries)} scraped entries.")
    success = regenerate_feed(comic_info, scraped_entries)

    if success:
        logger.info(f"Successfully regenerated feed for {comic_info['name']}")
    else:
        logger.error(f"Failed to regenerate feed for {comic_info['name']}")
        
    return success

def cleanup_old_tokens():
    """Remove tokens older than 7 days."""
    try:
        token_dir = 'tokens'
        if not os.path.exists(token_dir):
            return
        
        for filename in os.listdir(token_dir):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(token_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            
            if datetime.now() - file_time > timedelta(days=7):
                os.remove(filepath)
                logger.info(f"Removed old token: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning up old tokens: {e}")

def should_regenerate_feed(comic_info):
    """Check if a feed should be regenerated based on time or entry count."""
    feed_path = os.path.join('public', 'feeds', f"{comic_info['slug']}.xml")
    
    # Always regenerate if feed doesn't exist
    if not os.path.exists(feed_path):
        return True
    
    try:
        # Check file modification time
        mtime = datetime.fromtimestamp(os.path.getmtime(feed_path))
        # Regenerate weekly
        if datetime.now() - mtime > timedelta(days=7):
            return True
        
        # Check number of entries
        feed = feedparser.parse(feed_path)
        # Regenerate if more than 100 entries (to maintain performance)
        if len(feed.entries) > 100:
            return True
            
    except Exception as e:
        logger.error(f"Error checking feed status for {comic_info['name']}: {e}")
        # If we can't check, default to not regenerating
        return False
    
    return False

def process_comic(comic):
    """Process a single comic."""
    try:
        logger.info(f"Processing {comic['name']}")
        update_feed(comic)
        logger.info(f"Successfully updated feed for {comic['name']} with new content")
        return True
    except Exception as e:
        logger.error(f"Error processing {comic['name']}: {e}")
        return False

def main():
    """Main function to update all comic feeds."""
    try:
        # Load comics list
        comics = load_comics_list()
        logger.info(f"Loaded {len(comics)} comics")
        
        # Process comics concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all comics for processing
            future_to_comic = {executor.submit(process_comic, comic): comic for comic in comics}
            
            # Process results as they complete
            successful = 0
            failed = 0
            for future in concurrent.futures.as_completed(future_to_comic):
                comic = future_to_comic[future]
                try:
                    if future.result():
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Error processing {comic['name']}: {e}")
                    failed += 1
            
            logger.info(f"Completed processing {len(comics)} comics: {successful} successful, {failed} failed")
        
        return 0
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 