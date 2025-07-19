"""
Abstract Base Scraper for ComicCaster.

This module provides the base interface for all comic scrapers,
enabling support for multiple comic sources (GoComics, Tinyview, etc.).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all comic scrapers.
    
    This class defines the common interface that all comic scrapers must implement,
    ensuring consistent behavior across different comic sources.
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        """Initialize the base scraper with common configuration.
        
        Args:
            base_url: The base URL for the comic source
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        logger.info(f"Initialized {self.__class__.__name__} with base_url={base_url}")
    
    @abstractmethod
    def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
        """Scrape a comic for a given date.
        
        This is the main entry point for scraping a comic. It should handle
        the entire scraping process and return standardized data.
        
        Args:
            comic_slug: The comic's identifier (e.g., 'garfield', 'nick-anderson')
            date: The date to scrape in YYYY/MM/DD format
            
        Returns:
            A dictionary with standardized comic data, or None if scraping fails.
            The dictionary should contain:
            - slug: The comic slug
            - date: The requested date
            - source: The source name (from get_source_name())
            - title: The comic title
            - url: The comic page URL
            - images: List of image dictionaries with 'url' and optional 'alt'
            - image_count: Number of images
            - published_date: DateTime object of publication
            - For single images: image_url and image_alt convenience fields
        """
        pass
    
    @abstractmethod
    def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
        """Fetch the HTML content of a comic page.
        
        Args:
            comic_slug: The comic's identifier
            date: The date in YYYY/MM/DD format
            
        Returns:
            The HTML content as a string, or None if fetching fails
        """
        pass
    
    @abstractmethod
    def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
        """Extract comic images from HTML content.
        
        Args:
            html_content: The HTML content to parse
            comic_slug: The comic's identifier
            date: The date string
            
        Returns:
            A list of dictionaries, each containing:
            - url: The image URL
            - alt: The alt text (optional)
            - title: The title text (optional)
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Get the source name for this scraper.
        
        Returns:
            The source identifier (e.g., 'gocomics-daily', 'gocomics-political', 'tinyview')
        """
        pass
    
    def build_comic_result(self, comic_slug: str, date: str, images: List[Dict[str, str]], 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build a standardized comic result dictionary.
        
        This helper method ensures consistent output format across all scrapers.
        
        Args:
            comic_slug: The comic's identifier
            date: The date string
            images: List of image dictionaries
            metadata: Optional additional metadata
            
        Returns:
            Standardized comic data dictionary
        """
        result = {
            'slug': comic_slug,
            'date': date,
            'source': self.get_source_name(),
            'images': images,
            'image_count': len(images)
        }
        
        # Add convenience fields for single-image comics
        if len(images) == 1:
            result['image_url'] = images[0]['url']
            result['image_alt'] = images[0].get('alt', '')
        
        # Merge in any additional metadata
        if metadata:
            result.update(metadata)
        
        return result