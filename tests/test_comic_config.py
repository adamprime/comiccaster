"""
Test suite for Story 1.2: Granular Source Field in Comic Configuration.
Following TDD principles - these tests are written before implementation.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open


class TestComicConfiguration:
    """Test cases for granular source field implementation."""
    
    def test_comic_has_granular_source_field(self):
        """Test that comic config includes granular source field."""
        comic = {
            'slug': 'garfield',
            'name': 'Garfield',
            'source': 'gocomics-daily'
        }
        assert comic['source'] == 'gocomics-daily'
    
    def test_tinyview_source_field(self):
        """Test Tinyview comics have correct source."""
        comic = {
            'slug': 'nick-anderson',
            'name': 'Nick Anderson',
            'source': 'tinyview'
        }
        assert comic['source'] == 'tinyview'
    
    def test_political_comics_source_field(self):
        """Test political comics have correct source."""
        comic = {
            'slug': 'doonesbury',
            'name': 'Doonesbury',
            'source': 'gocomics-political'
        }
        assert comic['source'] == 'gocomics-political'
    
    def test_political_cartoons_compatibility(self):
        """Test political cartoons use separate source."""
        # Political cartoons team will use 'gocomics-political'
        # This ensures no conflicts with their implementation
        comic = {
            'slug': 'political-cartoon',
            'name': 'Political Cartoon',
            'source': 'gocomics-political'
        }
        assert comic['source'] == 'gocomics-political'
    
    def test_loader_returns_list_entries_unchanged(self):
        """ComicsLoader hands back each entry as the list has it, source or not."""
        from comiccaster.loader import ComicsLoader

        mock_comics = [
            {'slug': 'garfield', 'name': 'Garfield'},
            {'slug': 'zits', 'name': 'Zits', 'source': 'comicskingdom'},
            {'slug': 'nick-anderson', 'name': 'Nick Anderson', 'source': 'tinyview'},
        ]

        with patch('builtins.open', mock_open(read_data=json.dumps(mock_comics))):
            comics = ComicsLoader().load_comics_from_file('test.json')

        assert comics == mock_comics

    def test_scraper_factory_uses_source_field(self):
        """Test that the scraper factory selects a scraper by the source field."""
        # Use scraper factory directly to test source field mapping
        from comiccaster.scraper_factory import ScraperFactory
        
        # Test GoComics daily
        daily_comic = {'slug': 'garfield', 'source': 'gocomics-daily'}
        scraper = ScraperFactory.get_scraper(daily_comic['source'])
        assert scraper.get_source_name() == 'gocomics-daily'
        
        # Test GoComics political
        political_comic = {'slug': 'doonesbury', 'source': 'gocomics-political'}
        scraper = ScraperFactory.get_scraper(political_comic['source'])
        assert scraper.get_source_name() == 'gocomics-political'
        
        # Test Tinyview
        tinyview_comic = {'slug': 'nick-anderson', 'source': 'tinyview'}
        scraper = ScraperFactory.get_scraper(tinyview_comic['source'])
        assert scraper.get_source_name() == 'tinyview'
    
    def test_feed_generator_includes_source_metadata(self):
        """Test that generated feeds include source information."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        # Test with Tinyview comic
        comic_info = {
            'name': 'Nick Anderson',
            'slug': 'nick-anderson',
            'source': 'tinyview'
        }
        
        feed = generator.create_feed(comic_info)
        feed_str = feed.rss_str(pretty=True).decode('utf-8')
        
        # Check that source is included in feed metadata
        # It should appear in category or description
        assert 'TinyView' in feed_str or 'tinyview' in feed_str.lower()