"""
Feed Aggregator Module for ComicCaster

This module combines multiple individual comic RSS feeds into a single combined feed.
It fetches the latest entries from each feed and merges them chronologically.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime
import feedgen
from feedgen.feed import FeedGenerator
from feedgen.entry import FeedEntry

class FeedAggregator:
    """Class to aggregate multiple RSS feeds into a single feed."""
    
    def __init__(self, feeds_dir='feeds'):
        """Initialize the feed aggregator.
        
        Args:
            feeds_dir (str): Directory containing individual comic feeds
        """
        self.feeds_dir = feeds_dir
        self.feed_generator = FeedGenerator()
        self.feed_generator.title('ComicCaster Combined Feed')
        self.feed_generator.description('A personalized feed of your favorite comics')
        self.feed_generator.link(href='https://example.com')
        self.feed_generator.language('en')
        
    def aggregate_feeds(self, comic_slugs, max_entries=50):
        """Aggregate multiple comic feeds into a single feed.
        
        Args:
            comic_slugs (list): List of comic slugs to include in the feed
            max_entries (int): Maximum number of entries to include in the combined feed
            
        Returns:
            str: XML string of the combined feed
        """
        # Reset the feed generator
        self.feed_generator = FeedGenerator()
        self.feed_generator.title('ComicCaster Combined Feed')
        self.feed_generator.description('A personalized feed of your favorite comics')
        self.feed_generator.link(href='https://example.com')
        self.feed_generator.language('en')
        
        # Collect all entries from the individual feeds
        all_entries = []
        
        for slug in comic_slugs:
            feed_path = os.path.join(self.feeds_dir, f'{slug}.xml')
            
            if not os.path.exists(feed_path):
                continue
                
            try:
                # Parse the individual feed
                tree = ET.parse(feed_path)
                root = tree.getroot()
                
                # Extract entries
                for item in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                    entry = FeedEntry()
                    
                    # Get title
                    title_elem = item.find('{http://www.w3.org/2005/Atom}title')
                    if title_elem is not None:
                        entry.title(title_elem.text)
                    
                    # Get link
                    link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                    if link_elem is not None:
                        entry.link(href=link_elem.get('href'))
                    
                    # Get published date
                    published_elem = item.find('{http://www.w3.org/2005/Atom}published')
                    if published_elem is not None:
                        entry.published(published_elem.text)
                    
                    # Get content
                    content_elem = item.find('{http://www.w3.org/2005/Atom}content')
                    if content_elem is not None:
                        entry.content(content_elem.text)
                    
                    # Add the comic slug as a category
                    entry.category(term=slug, label=slug)
                    
                    all_entries.append(entry)
            except Exception as e:
                print(f"Error processing feed for {slug}: {e}")
        
        # Sort entries by published date (newest first)
        all_entries.sort(key=lambda x: x.published(), reverse=True)
        
        # Add entries to the feed generator (up to max_entries)
        for entry in all_entries[:max_entries]:
            self.feed_generator.add_entry(entry)
        
        # Generate the feed
        return self.feed_generator.rss_str(pretty=True).decode('utf-8')
    
    def save_combined_feed(self, comic_slugs, output_path, max_entries=50):
        """Aggregate feeds and save the combined feed to a file.
        
        Args:
            comic_slugs (list): List of comic slugs to include in the feed
            output_path (str): Path to save the combined feed
            max_entries (int): Maximum number of entries to include in the combined feed
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            feed_xml = self.aggregate_feeds(comic_slugs, max_entries)
            
            with open(output_path, 'w') as f:
                f.write(feed_xml)
                
            return True
        except Exception as e:
            print(f"Error saving combined feed: {e}")
            return False 