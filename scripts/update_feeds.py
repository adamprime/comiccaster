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
MAX_WORKERS = 10  # Maximum number of concurrent workers
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

def get_headers():
    """Get browser-like headers for HTTP requests."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

def scrape_comic(comic, date_str, timeout=REQUEST_TIMEOUT, retries=MAX_RETRIES):
    """Scrape a comic from GoComics for a given date."""
    logging.info(f"Fetching {comic['name']} for {date_str}")
    
    # Define target_date early based on input date_str format
    try:
        if '/' in date_str:
            # Input is YYYY/MM/DD
            target_date = datetime.strptime(date_str, '%Y/%m/%d').date()
            url_date_str = date_str # Already in correct format for URL
        else:
            # Assume input is YYYY-MM-DD or similar parseable format
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            url_date_str = target_date.strftime('%Y/%m/%d') # Convert to URL format
        
        url = f"https://www.gocomics.com/{comic['slug']}/{url_date_str}"
        # Ensure pub_date_str uses YYYY-MM-DD format for consistency later
        pub_date_str_for_return = target_date.strftime('%Y-%m-%d') 

    except ValueError as e:
        logging.error(f"Error parsing date string '{date_str}' for {comic['name']}: {e}")
        return None # Cannot proceed without a valid date
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract the comic image URL (prioritizing the actual comic)
            comic_image = None

            # === NEW ORDER: Method 1 - Try finding the specific comic strip image tag by class, src host, AND fetchpriority ===
            # Add fetchpriority='high' to the selector for more specificity
            specific_selector = 'img.Comic_comic__image_strip__hPLFq[src*="featureassets.gocomics.com/assets/"][fetchpriority="high"]'
            img_tag = soup.select_one(specific_selector)
            if img_tag and img_tag.get('src'):
                # Found the specific image tag, extract its src
                comic_image = img_tag['src']
                logging.info(f"Found actual comic image via specific img tag selector (class, src, fetchpriority) for {url}")
            # else:
                # logging.info(f"Specific comic img tag ({specific_selector}) not found. Trying JSON-LD.")

            # === Method 2 (Fallback 1) - Try JSON-LD if specific img tag failed ===
            if not comic_image:
                potential_json_images = [] # Store candidates from JSON-LD
                scripts = soup.find_all("script", type="application/ld+json")
                for script in scripts:
                    try:
                        if script.string and "ImageObject" in script.string and "contentUrl" in script.string:
                            data = json.loads(script.string)
                            # Check if it's an ImageObject with a featureassets URL
                            if data.get("@type") == "ImageObject" and data.get("contentUrl") and "featureassets.gocomics.com" in data.get("contentUrl"):
                                potential_json_images.append({'url': data.get("contentUrl"), 'json': data})
                    except Exception as e:
                        logging.warning(f"Error parsing JSON data in script tag: {e}")
                
                # Now, choose the best image from the potential JSON candidates
                if potential_json_images:
                    found_match_by_date = False
                    for item in potential_json_images:
                        caption = item['json'].get('caption', '')
                        name = item['json'].get('name', '')
                        if pub_date_str_for_return in caption or pub_date_str_for_return in name:
                            comic_image = item['url']
                            logging.info(f"Found actual comic image in JSON data (matched date {pub_date_str_for_return}) for {url}")
                            found_match_by_date = True
                            break
                    if not found_match_by_date:
                        comic_image = potential_json_images[0]['url']
                        logging.warning(f"Could not confirm date in JSON metadata for {url}. Using first found featureassets URL from JSON-LD: {comic_image}")
                # else: # Optional log if JSON-LD also yields nothing
                    # logging.info(f"No suitable image found in JSON-LD for {url}. Trying script regex.")

            # === Method 3 (Fallback 2) - Try regex in other scripts ===
            if not comic_image:
                for script in soup.find_all("script"):
                    if script.string and "featureassets.gocomics.com/assets" in script.string and "url" in script.string:
                        try:
                            # Find URLs that look like comic strip images
                            matches = re.findall(r'"url"\s*:\s*"(https://featureassets\.gocomics\.com/assets/[^"]+)"', script.string)
                            if matches:
                                comic_image = matches[0]
                                logging.info(f"Found comic image URL in script data for {url}")
                                break
                        except Exception as e:
                            logging.warning(f"Error extracting URL from script: {e}")
            
            # === Method 4 (Fallback 3) - Try og:image ===
            # Original Method 3/4 combined (img tag check removed as it's now Method 1)
            # Method 4: If no comic image found yet, try the social media image as fallback
            if not comic_image:
                meta_tag = soup.select_one('meta[property="og:image"]')
                if meta_tag and meta_tag.get("content"):
                    comic_image = meta_tag["content"]
                    logging.info(f"Found social media image for {url}")
            
            if not comic_image:
                logging.error(f"No comic image found for {url}")
                return None
            
            # Get the comic URL (which might be different than the constructed URL)
            comic_url = url
            
            # Create title from date
            title = f"{comic['name']} - {target_date.strftime('%Y-%m-%d')}"
            
            # Don't include the image in the description, as it will be handled separately
            description_text = f'Comic strip for {target_date.strftime("%Y-%m-%d")}'
            
            # Use the image URL for the image field, but don't duplicate it in the description
            # This will prevent the image from appearing twice in the feed
            return {
                'title': title,
                'url': url,
                'image': comic_image,
                'pub_date': pub_date_str_for_return, # Use the consistently formatted YYYY-MM-DD string
                'description': description_text,
                'id': url  # Use URL as ID to ensure uniqueness
            }
            
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(1)  # Wait before retrying
                continue
            logging.warning(f"Failed to fetch {comic['name']} for {date_str} after {retries} attempts: {str(e)}")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error fetching {comic['name']} for {date_str}: {str(e)}")
            return None

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