"""
Comic Scraper Module - Backward Compatibility

This module provides backward compatibility by importing the GoComicsScraper
as ComicScraper. New code should use gocomics_scraper.GoComicsScraper directly.
"""

# Import the new scraper and provide backward compatibility
from .gocomics_scraper import GoComicsScraper as ComicScraper

# For complete backward compatibility, also expose the class under its new name
from .gocomics_scraper import GoComicsScraper

__all__ = ['ComicScraper', 'GoComicsScraper']