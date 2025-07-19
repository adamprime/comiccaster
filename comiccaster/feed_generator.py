"""
Feed Generator Module

This module handles generating RSS feeds for individual comics.
It uses the feedgen library to create valid RSS feeds with comic entries.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import time
import feedparser
from email.utils import parsedate_to_datetime
import re
import pytz

from feedgen.feed import FeedGenerator
from feedgen.entry import FeedEntry

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComicFeedGenerator:
    """Handles generating RSS feeds for individual comics."""
    
    def __init__(self, base_url: str = "https://www.gocomics.com", output_dir: str = "feeds"):
        """
        Initialize the ComicFeedGenerator.
        
        Args:
            base_url (str): The base URL for GoComics. Defaults to "https://www.gocomics.com".
            output_dir (str): Directory to store generated feeds. Defaults to "feeds".
        """
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_feed(self, comic_info: Dict[str, str]) -> FeedGenerator:
        """
        Create a new feed for a comic.
        
        Args:
            comic_info (Dict[str, str]): Dictionary containing comic information.
            
        Returns:
            FeedGenerator: A configured feed generator instance.
        """
        fg = FeedGenerator()
        
        # Get source information
        source = comic_info.get('source', 'gocomics-daily')
        source_display = {
            'gocomics-daily': 'GoComics',
            'gocomics-political': 'GoComics Political',
            'tinyview': 'TinyView'
        }.get(source, 'GoComics')
        
        # Set feed metadata
        fg.title(f"{comic_info['name']} - {source_display}")
        fg.description(f"Daily {comic_info['name']} comic strip by {comic_info.get('author', 'Unknown Author')} from {source_display}")
        fg.language('en')
        
        # Add source as a category
        fg.category(term=source, label=source_display)
        
        # Set feed ID and updated time
        fg.id(comic_info['url'])
        fg.updated(datetime.now(timezone.utc))
        
        # Add feed author
        if comic_info.get('author'):
            fg.author({'name': comic_info['author']})
        
        # Add atom:link for feed self-reference
        feed_url = f"https://comiccaster.xyz/feeds/{comic_info['slug']}.xml"
        fg.link(href=feed_url, rel='self', type='application/rss+xml')
        
        # Set the main feed link to the comic's URL (this must come after the self-reference)
        fg.link(href=comic_info['url'])
        
        return fg
    
    def parse_date_with_timezone(self, date_str: str) -> datetime:
        """
        Parse a date string and ensure it has timezone information.
        
        Args:
            date_str (str): Date string in RFC 2822 or ISO format (YYYY-MM-DD).
            
        Returns:
            datetime: Datetime object with timezone information.
        """
        try:
            # If date_str is already a datetime object, just ensure it has timezone
            if isinstance(date_str, datetime):
                dt = date_str
            else:
                # First try to parse RFC 2822 date string
                try:
                    dt = parsedate_to_datetime(date_str)
                except Exception:
                    # If that fails, try ISO format
                    try:
                        # Try simple ISO format first
                        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                            # For simple ISO format, create naive datetime and localize to UTC
                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                            dt = pytz.UTC.localize(dt)
                        else:
                            # Use dateutil parser as a last resort
                            from dateutil import parser as date_parser
                            dt = date_parser.parse(date_str)
                            if dt.tzinfo is None:
                                dt = pytz.UTC.localize(dt)
                    except Exception as e:
                        logger.error(f"Failed to parse date string '{date_str}': {e}")
                        # Return current time as fallback
                        dt = datetime.now(pytz.UTC)
            
            # Ensure the datetime has timezone information
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            
            return dt
            
        except Exception as e:
            logger.error(f"Error parsing date '{date_str}': {e}")
            return datetime.now(pytz.UTC)
    
    def create_entry(self, comic_info, metadata):
        """Create a feed entry from comic metadata."""
        entry = FeedEntry()
        
        # Parse the publication date
        pub_date = self.parse_date_with_timezone(metadata.get('pub_date', ''))
        
        # Create title with the correct date format
        title = metadata.get('title', f"{comic_info['name']} - {pub_date.strftime('%Y-%m-%d')}")
        entry.title(title)
        
        # Set the entry URL
        entry.link(href=metadata.get('url', comic_info['url']))
        
        # Get image URL from either image or image_url field
        image_url = metadata.get('image_url', metadata.get('image', ''))
        
        # Create description with image and alt text
        description = metadata.get('description', '')
        if image_url:
            # Only add the image tag if it's not already in the description
            if '<img' not in description:
                description = f"""
                <div style="text-align: center;">
                    <img src="{image_url}" alt="{comic_info['name']}" style="max-width: 100%;">
                    <p>{description}</p>
                </div>
                """
            entry.enclosure(image_url, 0, 'image/jpeg')
        
        entry.description(description)
        
        # Set publication date
        entry.published(pub_date)
        
        # Set unique ID
        entry.id(metadata.get('id', metadata.get('url', f"{comic_info['url']}#{pub_date.isoformat()}")))
        
        return entry
    
    def update_feed(self, comic_info: Dict[str, str], metadata: Dict[str, str]) -> bool:
        """
        Update a comic's feed with a new entry.
        
        Args:
            comic_info (Dict[str, str]): Dictionary containing comic information.
            metadata (Dict[str, str]): Dictionary containing comic strip metadata.
            
        Returns:
            bool: True if the feed was updated successfully, False otherwise.
        """
        try:
            feed_path = self.output_dir / f"{comic_info['slug']}.xml"
            
            # Create new feed or load existing one
            fg = self.create_feed(comic_info)
            existing_entries = []  # Track existing entries with their dates
            
            # If feed exists, load existing entries
            if feed_path.exists():
                try:
                    existing_feed = feedparser.parse(str(feed_path))
                    for entry in existing_feed.entries:
                        try:
                            # Get publication date
                            if hasattr(entry, 'published_parsed'):
                                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                                if pub_date.tzinfo is None:
                                    pub_date = pytz.UTC.localize(pub_date)
                            else:
                                pub_date = datetime.now(pytz.UTC)
                            
                            # Store entry with its date
                            existing_entries.append({
                                'entry': entry,
                                'date': pub_date
                            })
                        except Exception as e:
                            logger.error(f"Error processing existing entry: {e}")
                            continue
                except Exception as e:
                    logger.error(f"Error loading existing feed: {e}")
            
            # Create new entry
            new_entry = self.create_entry(comic_info, metadata)
            
            # Add new entry to feed
            fg.add_entry(new_entry)
            
            # Add existing entries, ensuring no duplicates
            new_pub_date = new_entry.published()
            for entry_data in existing_entries:
                if entry_data['date'] != new_pub_date:
                    fg.add_entry(entry_data['entry'])
            
            # Save the feed
            fg.rss_file(str(feed_path))
            return True
            
        except Exception as e:
            logger.error(f"Error updating feed for {comic_info['name']}: {e}")
            return False
    
    def generate_feed(self, comic_info: Dict[str, str], entries: List[Dict[str, str]]) -> bool:
        """
        Generate a complete feed for a comic with multiple entries.
        
        Args:
            comic_info (Dict[str, str]): Dictionary containing comic information.
            entries (List[Dict[str, str]]): List of comic strip metadata dictionaries.
            
        Returns:
            bool: True if the feed was generated successfully, False otherwise.
        """
        try:
            # Create new feed
            fg = self.create_feed(comic_info)
            
            # Create a list to store entries with parsed dates
            entries_with_dates = []
            seen_dates = {}  # Track entries by date to prevent duplicates
            
            # Process entries and parse their dates
            for metadata in entries:
                try:
                    # Parse the publication date
                    pub_date = self.parse_date_with_timezone(metadata.get('pub_date', ''))
                    date_str = pub_date.strftime('%Y-%m-%d')
                    
                    # Skip if we already have a more recent entry for this date
                    if date_str in seen_dates:
                        existing_date = seen_dates[date_str]['pub_date']
                        if pub_date <= existing_date:
                            logger.debug(f"Skipping duplicate entry for {date_str}")
                            continue
                    
                    # Store the entry with its date
                    entries_with_dates.append({
                        'metadata': metadata,
                        'pub_date': pub_date
                    })
                    seen_dates[date_str] = {
                        'metadata': metadata,
                        'pub_date': pub_date
                    }
                except Exception as e:
                    logger.error(f"Error processing entry: {e}")
                    continue
            
            # Add entries to feed (iterating over the potentially pre-sorted list)
            feed_entry_count = 0
            for entry_data in entries_with_dates: # Iterate over the list as received
                try:
                    # Create entry with the metadata
                    fe = self.create_entry(comic_info, entry_data['metadata'])
                    # Add entry to the feed
                    fg.add_entry(fe)
                    feed_entry_count += 1
                    logger.debug(f"Added entry: {entry_data['metadata'].get('title')} - {entry_data['pub_date']}")
                except Exception as entry_error:
                    logger.error(f"Error adding entry to feed: {entry_error}")
                    continue
            
            # Save the feed as RSS
            feed_path = self.output_dir / f"{comic_info['slug']}.xml"
            fg.rss_file(str(feed_path))
            logger.info(f"Generated feed for {comic_info['name']} at {feed_path} with {feed_entry_count} entries")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating feed for {comic_info['name']}: {e}")
            return False

def main():
    """Main function to demonstrate the ComicFeedGenerator usage."""
    try:
        # Example comic info
        comic_info = {
            'name': 'Garfield',
            'author': 'Jim Davis',
            'url': 'https://www.gocomics.com/garfield',
            'slug': 'garfield'
        }
        
        # Example metadata
        metadata = {
            'title': 'Garfield - 2024-04-06',
            'url': 'https://www.gocomics.com/garfield/2024/04/06',
            'image': 'https://gocomicscmsassets.gocomics.com/staging-assets/assets/GC_Social_FB_Garfield_8df2215f8b.jpg',
            'description': 'Garfield comic strip for April 6, 2024',
            'pub_date': 'Sat, 06 Apr 2024 00:00:00 -0400'
        }
        
        # Create generator and update feed
        generator = ComicFeedGenerator()
        generator.update_feed(comic_info, metadata)
        
    except Exception as e:
        logger.error(f"Failed to demonstrate feed generator: {e}")
        raise

if __name__ == "__main__":
    main() 