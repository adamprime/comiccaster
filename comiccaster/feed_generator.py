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
        fg.description(f"Daily {comic_info['name']} comic strip by {comic_info['author']}")
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
        
        # Set entry metadata
        fe.title(metadata.get('title', f"{comic_info['name']} - {datetime.now().strftime('%Y-%m-%d')}"))
        fe.link(href=metadata.get('url', comic_info['url']))
        
        # Set entry ID (using URL as permanent identifier)
        fe.id(metadata.get('url', comic_info['url']))
        
        # Create HTML description with the comic image
        description = f"""
        <div style="text-align: center;">
            <img src="{metadata.get('image', '')}" alt="{comic_info['name']}" style="max-width: 100%;">
            <p>{metadata.get('description', '')}</p>
        </div>
        """
        fe.description(description)
        
        # Set publication date if available
        if 'pub_date' in metadata:
            try:
                # Parse the RFC 2822 date string
                pub_date = datetime.strptime(metadata['pub_date'], '%a, %d %b %Y %H:%M:%S %z')
                fe.published(pub_date)
                fe.updated(pub_date)
            except ValueError:
                logger.warning(f"Could not parse publication date: {metadata['pub_date']}")
                # Use current time as fallback
                now = datetime.now(timezone.utc)
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
            
            # If feed exists, load existing entries
            if feed_path.exists():
                existing_feed = feedparser.parse(str(feed_path))
                for entry in existing_feed.entries:
                    fe = fg.add_entry()
                    fe.id(entry.id)
                    fe.title(entry.title)
                    fe.link(href=entry.link)
                    fe.description(entry.description)
                    if hasattr(entry, 'published_parsed'):
                        pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        fe.published(pub_date)
                        fe.updated(pub_date)
            
            # Create and add new entry
            fe = self.create_entry(comic_info, metadata)
            fg.add_entry(fe)
            
            # Save the feed as RSS
            fg.rss_file(str(feed_path))
            logger.info(f"Updated feed for {comic_info['name']} at {feed_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update feed for {comic_info['name']}: {e}")
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