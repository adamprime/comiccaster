#!/usr/bin/env python3
import os
import logging
import sys
from datetime import datetime, timezone, timedelta
import pytz
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from comiccaster.feed_generator import ComicFeedGenerator
import json
import re
from urllib.parse import urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def scrape_comic(slug, url=None, target_date=None):
    """
    Scrape a comic strip from GoComics.
    
    Args:
        slug (str): The comic slug.
        url (str, optional): Full URL to scrape. If not provided, it will be constructed.
        target_date (datetime, optional): Target date to scrape. If not provided, today's date is used.
    
    Returns:
        dict: Dictionary containing comic metadata, or None if an error occurred.
    """
    # Use current date if target_date not provided
    if target_date is None:
        target_date = datetime.now(timezone.utc)
    
    # Format the date for the URL
    date_str = target_date.strftime("%Y/%m/%d")
    
    # Construct the URL if not provided
    if url is None:
        url = f"https://www.gocomics.com/{slug}/{date_str}"
    
    # Request headers to mimic a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for 4XX/5XX status codes
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract the comic image URL (prioritizing the actual comic)
        comic_image = None
        
        # Try to find the comic image URL in the JSON data embedded in script tags
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                if script.string and "ImageObject" in script.string and "contentUrl" in script.string:
                    data = json.loads(script.string)
                    if data.get("@type") == "ImageObject" and data.get("contentUrl"):
                        content_url = data.get("contentUrl")
                        parsed_url = urlparse(content_url)
                        if parsed_url.hostname and (parsed_url.hostname == 'gocomics.com' or parsed_url.hostname.endswith('.gocomics.com')):
                            comic_image = data.get("contentUrl")
                            logger.info(f"Found actual comic image in JSON data for {url}")
                            break
            except Exception as e:
                logger.warning(f"Error parsing JSON data in script tag: {e}")
        
        # Try to extract from JSON data within Next.js script payloads
        if not comic_image:
            for script in soup.find_all("script"):
                if script.string and "gocomics.com/assets" in script.string and "url" in script.string:
                    try:
                        # Find URLs that look like comic strip images
                        matches = re.findall(r'"url"\s*:\s*"(https://featureassets\.gocomics\.com/assets/[^"]+)"', script.string)
                        if matches:
                            comic_image = matches[0]
                            logger.info(f"Found comic image URL in script data for {url}")
                            break
                    except Exception as e:
                        logger.warning(f"Error extracting URL from script: {e}")
        
        # If no comic image found in scripts, try the social media image as fallback
        if not comic_image:
            meta_tag = soup.select_one('meta[property="og:image"]')
            if meta_tag and meta_tag.get("content"):
                comic_image = meta_tag["content"]
                logger.info(f"Found social media image for {url}")
        
        if not comic_image:
            logger.error(f"No comic image found for {url}")
            return None
        
        # Get the comic URL (which might be different than the constructed URL)
        comic_url = url
        
        # Parse publication date from URL
        pub_date_str = date_str.replace("/", "-")
        
        # Create title from date
        title = f"{slug.replace('-', ' ').title()} - {target_date.strftime('%Y-%m-%d')}"
        
        # Don't include the image in the description, as it will be handled separately
        description_text = f'Comic strip for {target_date.strftime("%Y-%m-%d")}'
        
        # Parse the date and convert to datetime and UTC
        pub_date = target_date.replace(tzinfo=pytz.UTC)
        
        # Use the image URL for the image field, but don't duplicate it in the description
        # This will prevent the image from appearing twice in the feed
        return {
            'title': title,
            'url': url,
            'image': comic_image,
            'pub_date': pub_date_str,
            'description': description_text,
            'id': url  # Use URL as ID to ensure uniqueness
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error scraping {url}: {e}")
        return None

def regenerate_adamathome_feed():
    """Regenerate the Adam@Home feed from scratch."""
    # Delete the existing feed file if it exists
    feed_path = Path("feeds/adamathome.xml")
    if feed_path.exists():
        feed_path.unlink()
        logger.info(f"Deleted existing feed file: {feed_path}")
    
    # Create feed generator
    feed_generator = ComicFeedGenerator(output_dir="feeds")
    
    # Comic info for Adam@Home
    comic_info = {
        "name": "Adam@Home",
        "slug": "adamathome",
        "url": "https://www.gocomics.com/adamathome",
        "author": "Unknown Author",
        "description": "Daily Adam@Home comic strip"
    }
    
    # Scrape the last 10 days
    entries = []
    today = datetime.now(timezone.utc)
    
    for i in range(10):
        target_date = today - timedelta(days=i)
        metadata = scrape_comic(comic_info["slug"], target_date=target_date)
        
        if metadata:
            logger.info(f"Successfully scraped {comic_info['name']} for {target_date.strftime('%Y/%m/%d')}")
            entries.append(metadata)
        else:
            logger.warning(f"Failed to scrape {comic_info['name']} for {target_date.strftime('%Y/%m/%d')}")
    
    # Generate the feed
    if entries:
        success = feed_generator.generate_feed(comic_info, entries)
        if success:
            logger.info(f"Successfully generated feed for {comic_info['name']} with {len(entries)} entries")
        else:
            logger.error(f"Failed to generate feed for {comic_info['name']}")
    else:
        logger.error(f"No entries found for {comic_info['name']}")

if __name__ == "__main__":
    regenerate_adamathome_feed() 