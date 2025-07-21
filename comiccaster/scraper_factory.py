"""
Scraper Factory Module

This module provides a centralized factory for creating and managing
comic scrapers based on source type. It implements a singleton pattern
for performance and provides a clean interface for scraper management.
"""

import logging
from typing import Dict, List, Optional, Any
import threading

from .base_scraper import BaseScraper
from .gocomics_scraper import GoComicsScraper
from .tinyview_scraper import TinyviewScraper

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Factory class for creating and managing comic scrapers.
    
    This class implements a singleton pattern to ensure that only one
    instance of each scraper type is created and reused across the application.
    """
    
    # Class-level cache for scraper instances
    _scrapers: Dict[str, BaseScraper] = {}
    _lock = threading.Lock()  # Thread safety
    
    # Supported source types
    _SUPPORTED_SOURCES = {
        'gocomics-daily': {'class': GoComicsScraper, 'args': {'source_type': 'gocomics-daily'}},
        'gocomics-political': {'class': GoComicsScraper, 'args': {'source_type': 'gocomics-political'}},
        'tinyview': {'class': TinyviewScraper, 'args': {}},
        'gocomics': {'class': GoComicsScraper, 'args': {'source_type': 'gocomics-daily'}}  # Backward compatibility
    }
    
    @classmethod
    def get_scraper(cls, source: str) -> BaseScraper:
        """
        Get a scraper instance for the specified source.
        
        Args:
            source (str): The source type (e.g., 'gocomics-daily', 'tinyview').
            
        Returns:
            BaseScraper: The appropriate scraper instance.
            
        Raises:
            ValueError: If the source is not supported.
        """
        # Validate input
        if not source or not isinstance(source, str) or not source.strip():
            raise ValueError("Source must be a non-empty string")
        
        source = source.strip()
        
        # Check if source is supported
        if not cls.is_supported(source):
            supported = list(cls._SUPPORTED_SOURCES.keys())
            raise ValueError(f"Unsupported source '{source}'. Supported sources: {supported}")
        
        # Thread-safe singleton pattern
        with cls._lock:
            # Check if scraper already exists in cache
            if source in cls._scrapers:
                logger.debug(f"Returning cached scraper for source: {source}")
                return cls._scrapers[source]
            
            # Create new scraper instance
            logger.info(f"Creating new scraper for source: {source}")
            source_config = cls._SUPPORTED_SOURCES[source]
            scraper_class = source_config['class']
            scraper_args = source_config['args']
            
            try:
                scraper = scraper_class(**scraper_args)
                cls._scrapers[source] = scraper
                logger.info(f"Successfully created {scraper_class.__name__} for source: {source}")
                return scraper
            except Exception as e:
                logger.error(f"Failed to create scraper for source {source}: {e}")
                raise ValueError(f"Failed to create scraper for source '{source}': {e}")
    
    @classmethod
    def get_scraper_for_comic(cls, comic: Dict[str, Any]) -> BaseScraper:
        """
        Get a scraper instance for a comic configuration.
        
        Args:
            comic (Dict[str, Any]): Comic configuration with 'source' field.
            
        Returns:
            BaseScraper: The appropriate scraper instance.
            
        Raises:
            ValueError: If the comic configuration is invalid.
        """
        if not isinstance(comic, dict):
            raise ValueError("Comic must be a dictionary")
        
        source = comic.get('source', 'gocomics-daily')
        return cls.get_scraper(source)
    
    @classmethod
    def is_supported(cls, source: str) -> bool:
        """
        Check if a source is supported by the factory.
        
        Args:
            source (str): The source type to check.
            
        Returns:
            bool: True if the source is supported, False otherwise.
        """
        if not source or not isinstance(source, str):
            return False
        
        return source.strip() in cls._SUPPORTED_SOURCES
    
    @classmethod
    def get_supported_sources(cls) -> List[str]:
        """
        Get a list of all supported source types.
        
        Returns:
            List[str]: List of supported source types.
        """
        # Return copy to prevent external modification
        return list(cls._SUPPORTED_SOURCES.keys())
    
    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear the scraper cache, forcing new instances to be created.
        
        This is useful for testing or when you need to reset the factory state.
        """
        with cls._lock:
            logger.info("Clearing scraper cache")
            # Close any scrapers that have cleanup methods
            for source, scraper in cls._scrapers.items():
                try:
                    if hasattr(scraper, 'close_driver'):
                        scraper.close_driver()
                except Exception as e:
                    logger.warning(f"Error closing scraper for {source}: {e}")
            
            cls._scrapers.clear()
            logger.info("Scraper cache cleared")
    
    @classmethod
    def get_cache_info(cls) -> Dict[str, Any]:
        """
        Get information about the current cache state.
        
        Returns:
            Dict[str, Any]: Information about cached scrapers.
        """
        with cls._lock:
            return {
                'cached_sources': list(cls._scrapers.keys()),
                'cache_size': len(cls._scrapers),
                'supported_sources': cls.get_supported_sources()
            }
    
    @classmethod
    def register_source(cls, source: str, scraper_class: type, scraper_args: Optional[Dict] = None) -> None:
        """
        Register a new source type with the factory.
        
        This allows for dynamic extension of supported sources.
        
        Args:
            source (str): The source identifier.
            scraper_class (type): The scraper class to use for this source.
            scraper_args (Optional[Dict]): Arguments to pass to the scraper constructor.
            
        Raises:
            ValueError: If the source is already registered or invalid.
        """
        if not source or not isinstance(source, str):
            raise ValueError("Source must be a non-empty string")
        
        if not issubclass(scraper_class, BaseScraper):
            raise ValueError("Scraper class must inherit from BaseScraper")
        
        source = source.strip()
        
        if source in cls._SUPPORTED_SOURCES:
            raise ValueError(f"Source '{source}' is already registered")
        
        with cls._lock:
            cls._SUPPORTED_SOURCES[source] = {
                'class': scraper_class,
                'args': scraper_args or {}
            }
            logger.info(f"Registered new source: {source} -> {scraper_class.__name__}")


# Convenience function for backward compatibility
def get_scraper_for_comic(comic: Dict[str, Any]) -> BaseScraper:
    """
    Convenience function to get a scraper for a comic.
    
    This function provides backward compatibility for existing code.
    
    Args:
        comic (Dict[str, Any]): Comic configuration.
        
    Returns:
        BaseScraper: The appropriate scraper instance.
    """
    return ScraperFactory.get_scraper_for_comic(comic)