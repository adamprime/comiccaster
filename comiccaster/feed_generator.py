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
        
        # Adjust description based on comic type
        if comic_info.get('is_political'):
            fg.description(f"Political editorial cartoon by {comic_info.get('author', comic_info['name'])} from {source_display}. May contain political content and commentary on current events.")
        else:
            fg.description(f"Daily {comic_info['name']} comic strip by {comic_info.get('author', 'Unknown Author')} from {source_display}")
        fg.language('en')
        
        # Add source as a category
        fg.category(term=source, label=source_display)
        
        # Set feed ID and updated time
        comic_url = comic_info.get('url', f"https://www.gocomics.com/{comic_info.get('slug', '')}")
        fg.id(comic_url)
        fg.updated(datetime.now(timezone.utc))
        
        # Add feed author
        if comic_info.get('author'):
            fg.author({'name': comic_info['author']})
        
        # Add categories
        if comic_info.get('is_political'):
            fg.category(term='political', label='Political Comics')
            fg.category(term='editorial', label='Editorial Cartoons')
        else:
            fg.category(term='comics', label='Comic Strips')
        
        # Set TTL based on update recommendation
        update_rec = comic_info.get('update_recommendation', 'daily')
        if update_rec == 'daily':
            fg.ttl('1440')  # 24 hours in minutes
        elif update_rec == 'weekly':
            fg.ttl('10080')  # 7 days in minutes
        else:
            # Smart/irregular - check every 2 days
            fg.ttl('2880')  # 48 hours in minutes
        
        # Add atom:link for feed self-reference
        feed_url = f"https://comiccaster.xyz/feeds/{comic_info['slug']}.xml"
        fg.link(href=feed_url, rel='self', type='application/rss+xml')
        
        # Set the main feed link to the comic's URL (this must come after the self-reference)
        comic_url = comic_info.get('url', f"https://www.gocomics.com/{comic_info.get('slug', '')}")
        fg.link(href=comic_url)
        
        return fg
    
    def _create_single_image_content(self, image_url: str, description: str, comic_info: Dict[str, str]) -> str:
        """Create HTML content for single image comics (backward compatibility)."""
        if '<img' not in description:
            return f"""
            <div style="text-align: center; margin: 10px 0;">
                <img src="{image_url}" 
                     alt="{comic_info.get('name', 'Comic')}" 
                     style="max-width: 100%; height: auto; display: block; margin: 0 auto;"
                     loading="lazy">
                {f'<p style="margin-top: 15px;">{description}</p>' if description else ''}
            </div>
            """
        return description
    
    def _create_multi_image_content(self, images: List[Dict[str, str]], description: str, comic_info: Dict[str, str]) -> str:
        """Create HTML content for multi-image comics with responsive gallery layout."""
        if not images:
            return description
        
        # Start building the gallery HTML
        gallery_html = '<div class="comic-gallery" style="text-align: center; margin: 10px 0;">\n'
        
        # Add description at the top if present
        if description:
            gallery_html += f'<p style="margin-bottom: 15px; font-style: italic;">{description}</p>\n'
        
        # Add each image with proper spacing and accessibility
        for i, image in enumerate(images):
            image_url = image.get('url', '')
            if not image_url:
                continue
                
            alt_text = image.get('alt', f"{comic_info.get('name', 'Comic')} - Panel {i+1}")
            title_text = image.get('title', '')
            
            # Create image with responsive design and accessibility
            img_style = (
                "max-width: 100%; "
                "height: auto; "
                "display: block; "
                "margin: 10px auto; "
                "border-radius: 4px; "
                "box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
            )
            
            gallery_html += f'    <div class="comic-panel" style="margin: 15px 0;">\n'
            gallery_html += f'        <img src="{image_url}" '
            gallery_html += f'alt="{alt_text}" '
            if title_text:
                gallery_html += f'title="{title_text}" '
            gallery_html += f'style="{img_style}" '
            gallery_html += f'loading="lazy">\n'
            
            # Add panel description if available in alt text (for screen readers)
            if alt_text and alt_text != f"{comic_info.get('name', 'Comic')} - Panel {i+1}":
                gallery_html += f'        <div class="panel-description" style="font-size: 0.9em; color: #666; margin-top: 5px; font-style: italic;">{alt_text}</div>\n'
            
            gallery_html += f'    </div>\n'
        
        gallery_html += '</div>\n'
        
        # Add responsive CSS for better mobile experience
        responsive_css = """
        <style>
        .comic-gallery { 
            max-width: 100%; 
            overflow-x: hidden; 
        }
        .comic-panel img { 
            max-width: 100% !important; 
            height: auto !important; 
        }
        @media (max-width: 600px) {
            .comic-gallery { margin: 5px 0; }
            .comic-panel { margin: 10px 0; }
            .panel-description { font-size: 0.8em; }
        }
        </style>
        """ + gallery_html
        
        return responsive_css
    
    def create_feed_object(self, comic_info: Dict[str, str]) -> FeedGenerator:
        """
        Alias for create_feed to support test compatibility.
        """
        return self.create_feed(comic_info)
    
    def add_feed_entry(self, feed: FeedGenerator, entry_data: Dict[str, str], comic_info: Dict[str, str]) -> FeedEntry:
        """
        Add an entry to a feed object.
        
        Args:
            feed: The FeedGenerator object
            entry_data: Entry metadata dictionary
            comic_info: Comic information dictionary
            
        Returns:
            FeedEntry: The created feed entry
        """
        entry = self.create_entry(comic_info, entry_data)
        feed.add_entry(entry)
        return entry
    
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
        """Create a feed entry from comic metadata with multi-image support."""
        entry = FeedEntry()
        
        # Parse the publication date
        pub_date = self.parse_date_with_timezone(metadata.get('pub_date', ''))
        
        # Create title with the correct date format
        title = metadata.get('title', f"{comic_info['name']} - {pub_date.strftime('%Y-%m-%d')}")
        entry.title(title)
        
        # Set the entry URL
        entry.link(href=metadata.get('url', comic_info.get('url', f"https://example.com/{comic_info.get('slug', 'comic')}")))
        
        # Handle both new multi-image format and legacy single image format
        description = metadata.get('description', '')
        
        # Check for new 'images' array format (multi-image support)
        images = metadata.get('images', [])
        if images and isinstance(images, list):
            # Multi-image comic
            description = self._create_multi_image_content(images, description, comic_info)
            
            # Add enclosure for the first image (RSS standard practice)
            if images and images[0].get('url'):
                entry.enclosure(images[0]['url'], 0, 'image/jpeg')
        else:
            # Backward compatibility: single image format
            image_url = metadata.get('image_url', metadata.get('image', ''))
            if image_url:
                description = self._create_single_image_content(image_url, description, comic_info)
                entry.enclosure(image_url, 0, 'image/jpeg')
        
        entry.description(description)
        
        # Set publication date
        entry.published(pub_date)
        
        # Set unique ID
        default_url = comic_info.get('url', f"https://example.com/{comic_info.get('slug', 'comic')}")
        entry.id(metadata.get('id', metadata.get('url', f"{default_url}#{pub_date.isoformat()}")))
        
        # Add categories based on comic type
        if comic_info.get('is_political'):
            entry.category(term='political', label='Political Comics')
        
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