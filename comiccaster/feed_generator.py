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
        
        # Set feed metadata
        fg.title(f"{comic_info['name']} - GoComics")
        fg.description(f"Daily {comic_info['name']} comic strip by {comic_info.get('author', 'Unknown Author')}")
        fg.language('en')
        
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
            date_str (str): Date string in RFC 2822 format.
            
        Returns:
            datetime: Datetime object with timezone information.
        """
        try:
            # Try to parse RFC 2822 date string
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                # If no timezone info, assume UTC
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
            return datetime.now(timezone.utc)
    
    def create_entry(self, comic_info: Dict[str, str], metadata: Dict[str, str]) -> FeedEntry:
        """
        Create a feed entry for a comic strip.
        
        Args:
            comic_info (Dict[str, str]): Dictionary containing comic information.
            metadata (Dict[str, str]): Dictionary containing comic strip metadata.
            
        Returns:
            FeedEntry: A configured feed entry.
        """
        fe = FeedEntry()
        
        try:
            # Set entry metadata
            title = metadata.get('title', '').strip()
            if not title:
                # Generate a stable title format using ISO date
                if metadata.get('pub_date'):
                    pub_date = self.parse_date_with_timezone(metadata['pub_date'])
                    title = f"{comic_info['name']} - {pub_date.strftime('%Y-%m-%d')}"
                else:
                    title = f"{comic_info['name']} - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            fe.title(title)
            
            # Set entry link
            url = metadata.get('url', '').strip() or comic_info['url']
            fe.link(href=url)
            
            # Generate a unique and stable ID
            if metadata.get('url'):
                entry_id = metadata['url']
            elif metadata.get('pub_date'):
                # Use publication date and URL for a stable ID
                pub_date = self.parse_date_with_timezone(metadata['pub_date'])
                entry_id = f"{url}#{pub_date.strftime('%Y%m%d')}"
            else:
                # Use title and URL as fallback
                entry_id = f"{url}#{title}"
            
            fe.id(entry_id)
            
            # Create HTML description with the comic image and proper error handling
            image_url = metadata.get('image', '').strip()
            description = ''
            
            if image_url:
                description = f"""
                <div style="text-align: center;">
                    <img src="{image_url}" alt="{title}" style="max-width: 100%;">
                """
                if metadata.get('description'):
                    description += f"<p>{metadata['description']}</p>"
                description += "</div>"
            else:
                description = f"<p>Comic image not available. Please visit <a href='{url}'>the comic page</a>.</p>"
            
            fe.description(description)
            
            # Set publication date with timezone information
            if 'pub_date' in metadata:
                pub_date = self.parse_date_with_timezone(metadata['pub_date'])
            else:
                pub_date = datetime.now(timezone.utc)
            
            fe.published(pub_date)
            fe.updated(pub_date)
            
            # Add additional metadata if available
            if metadata.get('author'):
                fe.author({'name': metadata['author']})
            
            return fe
            
        except Exception as e:
            logger.error(f"Error creating feed entry: {e}")
            # Create a minimal valid entry as fallback
            now = datetime.now(timezone.utc)
            fe.title(f"{comic_info['name']} - {now.strftime('%Y-%m-%d')}")
            fe.link(href=comic_info['url'])
            fe.id(f"{comic_info['url']}#{now.strftime('%Y%m%d%H%M%S')}")
            fe.description(f"Error loading comic: {comic_info['name']}. Please visit <a href='{comic_info['url']}'>the comic page</a>.")
            fe.published(now)
            fe.updated(now)
            return fe
    
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
            existing_entries = set()  # Track existing entry IDs
            
            # If feed exists, load existing entries
            if feed_path.exists():
                try:
                    existing_feed = feedparser.parse(str(feed_path))
                    for entry in existing_feed.entries:
                        try:
                            fe = fg.add_entry()
                            # Ensure entry has an ID, generate one if missing
                            entry_id = getattr(entry, 'id', None)
                            if not entry_id:
                                # Generate a stable ID based on title and link
                                title = getattr(entry, 'title', '')
                                link = getattr(entry, 'link', '')
                                entry_id = f"{comic_info['url']}#{title}#{link}"
                            
                            existing_entries.add(entry_id)
                            fe.id(entry_id)
                            
                            fe.title(getattr(entry, 'title', f"{comic_info['name']} - Unknown Date"))
                            fe.link(href=getattr(entry, 'link', comic_info['url']))
                            fe.description(getattr(entry, 'description', ''))
                            
                            # Handle publication date with timezone
                            if hasattr(entry, 'published_parsed'):
                                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                                if pub_date.tzinfo is None:
                                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                            else:
                                pub_date = datetime.now(timezone.utc)
                            
                            fe.published(pub_date)
                            fe.updated(pub_date)
                            
                        except Exception as entry_error:
                            logger.warning(f"Error loading entry from existing feed: {entry_error}")
                            continue
                            
                except Exception as feed_error:
                    logger.error(f"Error loading existing feed: {feed_error}")
            
            # Create and add new entry
            new_entry = self.create_entry(comic_info, metadata)
            
            # Check if entry already exists
            new_entry_id = new_entry.id()
            if new_entry_id not in existing_entries:
                fg.add_entry(new_entry)
                logger.info(f"Added new entry with ID: {new_entry_id}")
            else:
                logger.info(f"Entry with ID {new_entry_id} already exists, skipping")
            
            # Save the feed as RSS
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
            
            # Add entries in reverse chronological order
            for metadata in sorted(entries, key=lambda x: x.get('pub_date', ''), reverse=True):
                fe = self.create_entry(comic_info, metadata)
                fg.add_entry(fe)
            
            # Save the feed as RSS
            feed_path = self.output_dir / f"{comic_info['slug']}.xml"
            fg.rss_file(str(feed_path))
            logger.info(f"Generated feed for {comic_info['name']} at {feed_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate feed for {comic_info['name']}: {e}")
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