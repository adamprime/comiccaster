"""
ComicCaster - A Python-based RSS feed generator for GoComics
"""

__version__ = "0.1.0"

# Import base classes and scrapers for easier access
from .base_scraper import BaseScraper
from .tinyview_scraper import TinyviewScraper

__all__ = ['BaseScraper', 'TinyviewScraper'] 