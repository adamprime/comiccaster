"""
Feed Aggregator Module

This module handles combining multiple comic feeds into a single feed.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import pytz
import feedparser
from feedgen.feed import FeedGenerator
from feedgen.entry import FeedEntry

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FeedAggregator:
    """Handles combining multiple comic feeds into a single feed."""
    
    def __init__(self, feeds_dir: str = 'feeds'):
        """
        Initialize the FeedAggregator.
        
        Args:
            feeds_dir (str): Directory containing the feed files. Defaults to 'feeds'.
        """
        self.feeds_dir = feeds_dir
        self.feed_generator = FeedGenerator()
        self.feed_generator.title('ComicCaster Combined Feed')
        self.feed_generator.description('A combined feed of your favorite comics')
        self.feed_generator.link(href='https://comiccaster.xyz')
        self.feed_generator.language('en')
        self.feed_generator.updated(datetime.now(pytz.UTC))
    
    def load_feed_entries(self, comic_slug: str) -> List[Dict[str, Any]]:
        """
        Load entries from a comic's feed file.
        
        Args:
            comic_slug (str): The slug identifier for the comic.
            
        Returns:
            List[Dict[str, Any]]: A list of feed entries as dictionaries.
        """
        feed_path = os.path.join(self.feeds_dir, f"{comic_slug}.xml")
        if not os.path.exists(feed_path):
            return []
            
        feed = feedparser.parse(feed_path)
        entries = []
        
        for entry in feed.entries:
            entries.append({
                'title': entry.title,
                'link': entry.link,
                'description': entry.description,
                'published': datetime.fromtimestamp(entry.published_parsed.timestamp()),
                'comic': comic_slug
            })
            
        return entries
    
    def add_entry(self, entry_data: Dict) -> None:
        """
        Add a comic entry to the feed.
        
        Args:
            entry_data (Dict): Dictionary containing entry information.
        """
        try:
            entry = FeedEntry()
            entry.title(entry_data.get('title', 'Untitled'))
            entry.link(href=entry_data.get('link', ''))
            entry.description(entry_data.get('description', ''))
            
            # Parse and set the publication date
            pub_date = entry_data.get('published')
            if pub_date:
                if isinstance(pub_date, str):
                    pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                entry.published(pub_date)
            
            self.feed_generator.entry(entry)
            
        except Exception as e:
            logger.error(f"Failed to add entry: {e}")
            raise
    
    def generate_feed(self, comic_slugs: List[str]) -> str:
        """
        Generate a combined feed from multiple comics.
        
        Args:
            comic_slugs (List[str]): List of comic slugs.
            
        Returns:
            str: The generated feed in RSS format.
        """
        try:
            # Load entries from all comics
            all_entries = []
            for slug in comic_slugs:
                entries = self.load_feed_entries(slug)
                all_entries.extend(entries)
            
            # Sort entries by publication date
            all_entries.sort(key=lambda x: x.get('published', ''), reverse=True)
            
            # Add entries to the feed
            for entry in all_entries:
                self.add_entry(entry)
            
            # Generate the feed
            return self.feed_generator.rss_str(pretty=True).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to generate feed: {e}")
            raise
    
    def save_feed(self, feed_content: str, output_file: str) -> None:
        """
        Save the generated feed to a file.
        
        Args:
            feed_content (str): The feed content to save.
            output_file (str): Path to the output file.
        """
        try:
            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(feed_content)
            
            logger.info(f"Saved feed to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save feed: {e}")
            raise 