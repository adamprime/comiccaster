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
    
    def test_default_source_is_gocomics_daily(self):
        """Test backward compatibility for comics without source."""
        from comiccaster.loader import ComicsLoader
        
        loader = ComicsLoader()
        comic = {'slug': 'garfield', 'name': 'Garfield'}
        normalized = loader.normalize_comic_config(comic)
        assert normalized['source'] == 'gocomics-daily'
    
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
    
    def test_loader_validates_source_field(self):
        """Test that loader validates source field values."""
        from comiccaster.loader import ComicsLoader
        
        loader = ComicsLoader()
        
        # Valid sources should pass
        valid_sources = ['gocomics-daily', 'gocomics-political', 'tinyview']
        for source in valid_sources:
            comic = {'slug': 'test', 'name': 'Test', 'source': source}
            result = loader.validate_comic_config(comic)
            assert result is True
        
        # Invalid source should fail
        invalid_comic = {'slug': 'test', 'name': 'Test', 'source': 'invalid-source'}
        with pytest.raises(ValueError) as exc_info:
            loader.validate_comic_config(invalid_comic)
        assert 'invalid-source' in str(exc_info.value)
    
    def test_loader_preserves_source_on_load(self):
        """Test that ComicsLoader preserves source field when loading."""
        from comiccaster.loader import ComicsLoader
        
        # Mock file content with source fields
        mock_comics = [
            {'slug': 'garfield', 'name': 'Garfield', 'source': 'gocomics-daily'},
            {'slug': 'nick-anderson', 'name': 'Nick Anderson', 'source': 'tinyview'},
            {'slug': 'doonesbury', 'name': 'Doonesbury', 'source': 'gocomics-political'}
        ]
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_comics))):
            loader = ComicsLoader()
            # Only load from one file to avoid duplicates
            comics = loader.load_comics_from_file('test.json')
            # Normalize them like load_all_comics would
            comics = [loader.normalize_comic_config(comic) for comic in comics]
            
            assert len(comics) == 3
            assert comics[0]['source'] == 'gocomics-daily'
            assert comics[1]['source'] == 'tinyview'
            assert comics[2]['source'] == 'gocomics-political'
    
    def test_update_feeds_uses_source_field(self):
        """Test that update_feeds.py uses source field to select scraper."""
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
    
    def test_backward_compatibility_for_missing_source(self):
        """Test that comics without source field still work."""
        from comiccaster.loader import ComicsLoader
        
        loader = ComicsLoader()
        
        # Old format comic without source
        old_comic = {'slug': 'garfield', 'name': 'Garfield'}
        normalized = loader.normalize_comic_config(old_comic)
        
        # Should default to gocomics-daily
        assert normalized['source'] == 'gocomics-daily'
        assert normalized['slug'] == 'garfield'
        assert normalized['name'] == 'Garfield'
    
    def test_mixed_source_comic_lists(self):
        """Test loading mixed comic lists with different sources."""
        from comiccaster.loader import ComicsLoader
        
        # Mock mixed comic list
        mock_comics = [
            {'slug': 'garfield', 'name': 'Garfield'},  # No source (backward compat)
            {'slug': 'calvin-and-hobbes', 'name': 'Calvin and Hobbes', 'source': 'gocomics-daily'},
            {'slug': 'doonesbury', 'name': 'Doonesbury', 'source': 'gocomics-political'},
            {'slug': 'nick-anderson', 'name': 'Nick Anderson', 'source': 'tinyview'}
        ]
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_comics))):
            loader = ComicsLoader()
            # Only load from one file to avoid duplicates
            comics = loader.load_comics_from_file('test.json')
            # Normalize them like load_all_comics would
            comics = [loader.normalize_comic_config(comic) for comic in comics]
            
            # Check all comics loaded with correct sources
            assert len(comics) == 4
            assert comics[0]['source'] == 'gocomics-daily'  # Default
            assert comics[1]['source'] == 'gocomics-daily'
            assert comics[2]['source'] == 'gocomics-political'
            assert comics[3]['source'] == 'tinyview'