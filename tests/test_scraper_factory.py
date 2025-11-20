"""
Test suite for Story 1.3: Scraper Factory.
Following TDD principles - these tests are written before implementation.
"""

import pytest
from unittest.mock import Mock, patch


class TestScraperFactory:
    """Test cases for the scraper factory implementation."""
    
    def test_factory_returns_gocomics_scraper_for_daily(self):
        """Test factory returns GoComics scraper for daily comics."""
        from comiccaster.scraper_factory import ScraperFactory
        
        scraper = ScraperFactory.get_scraper('gocomics-daily')
        assert scraper.__class__.__name__ == 'GoComicsScraper'
        assert scraper.get_source_name() == 'gocomics-daily'
    
    def test_factory_returns_gocomics_scraper_for_political(self):
        """Test factory returns GoComics scraper for political cartoons."""
        from comiccaster.scraper_factory import ScraperFactory
        
        scraper = ScraperFactory.get_scraper('gocomics-political')
        assert scraper.__class__.__name__ == 'GoComicsScraper'
        assert scraper.get_source_name() == 'gocomics-political'
    
    def test_factory_returns_tinyview_scraper(self):
        """Test factory returns Tinyview scraper for tinyview source."""
        from comiccaster.scraper_factory import ScraperFactory
        
        scraper = ScraperFactory.get_scraper('tinyview')
        assert scraper.__class__.__name__ == 'TinyviewScraper'
        assert scraper.get_source_name() == 'tinyview'
    
    def test_factory_raises_for_unknown_source(self):
        """Test factory raises exception for unknown source."""
        from comiccaster.scraper_factory import ScraperFactory
        
        with pytest.raises(ValueError) as exc_info:
            ScraperFactory.get_scraper('unknown-source')
        
        assert 'unknown-source' in str(exc_info.value).lower()
    
    def test_factory_backward_compatibility(self):
        """Test factory handles legacy 'gocomics' source."""
        from comiccaster.scraper_factory import ScraperFactory
        
        # Should default to gocomics-daily
        scraper = ScraperFactory.get_scraper('gocomics')
        assert scraper.__class__.__name__ == 'GoComicsScraper'
        assert scraper.get_source_name() == 'gocomics-daily'
    
    def test_factory_singleton_pattern(self):
        """Test factory maintains single instance per source type."""
        from comiccaster.scraper_factory import ScraperFactory
        
        # Get same scraper type multiple times
        scraper1 = ScraperFactory.get_scraper('gocomics-daily')
        scraper2 = ScraperFactory.get_scraper('gocomics-daily')
        
        # Should be the same instance (singleton pattern)
        assert scraper1 is scraper2
    
    def test_factory_different_instances_for_different_sources(self):
        """Test factory creates different instances for different sources."""
        from comiccaster.scraper_factory import ScraperFactory
        
        daily_scraper = ScraperFactory.get_scraper('gocomics-daily')
        political_scraper = ScraperFactory.get_scraper('gocomics-political')
        tinyview_scraper = ScraperFactory.get_scraper('tinyview')
        
        # Should be different instances
        assert daily_scraper is not political_scraper
        assert daily_scraper is not tinyview_scraper
        assert political_scraper is not tinyview_scraper
        
        # But should have different source names
        assert daily_scraper.get_source_name() == 'gocomics-daily'
        assert political_scraper.get_source_name() == 'gocomics-political'
        assert tinyview_scraper.get_source_name() == 'tinyview'
    
    def test_factory_clear_cache(self):
        """Test factory can clear its cache of scrapers."""
        from comiccaster.scraper_factory import ScraperFactory
        
        # Get a scraper
        scraper1 = ScraperFactory.get_scraper('gocomics-daily')
        
        # Clear cache
        ScraperFactory.clear_cache()
        
        # Get same type again - should be different instance
        scraper2 = ScraperFactory.get_scraper('gocomics-daily')
        
        assert scraper1 is not scraper2
        assert scraper1.get_source_name() == scraper2.get_source_name()
    
    def test_factory_get_all_supported_sources(self):
        """Test factory can list all supported sources."""
        from comiccaster.scraper_factory import ScraperFactory
        
        sources = ScraperFactory.get_supported_sources()
        
        expected_sources = ['gocomics-daily', 'gocomics-political', 'tinyview', 'gocomics', 'farside-daily', 'farside-new']
        assert set(sources) == set(expected_sources)
    
    def test_factory_supports_source_checking(self):
        """Test factory can check if a source is supported."""
        from comiccaster.scraper_factory import ScraperFactory
        
        # Valid sources
        assert ScraperFactory.is_supported('gocomics-daily')
        assert ScraperFactory.is_supported('gocomics-political')
        assert ScraperFactory.is_supported('tinyview')
        assert ScraperFactory.is_supported('gocomics')  # Backward compatibility
        assert ScraperFactory.is_supported('farside-daily')
        assert ScraperFactory.is_supported('farside-new')
        
        # Invalid sources
        assert not ScraperFactory.is_supported('invalid-source')
        assert not ScraperFactory.is_supported('unknown')
        assert not ScraperFactory.is_supported('')
    
    def test_factory_inherits_from_base_scraper(self):
        """Test that all scrapers returned by factory inherit from BaseScraper."""
        from comiccaster.scraper_factory import ScraperFactory
        from comiccaster.base_scraper import BaseScraper
        
        sources = ['gocomics-daily', 'gocomics-political', 'tinyview']
        
        for source in sources:
            scraper = ScraperFactory.get_scraper(source)
            assert isinstance(scraper, BaseScraper)
    
    def test_factory_integration_with_comic_config(self):
        """Test factory integration with comic configuration objects."""
        from comiccaster.scraper_factory import ScraperFactory
        
        # Test with various comic configurations
        comic_configs = [
            {'slug': 'garfield', 'source': 'gocomics-daily'},
            {'slug': 'doonesbury', 'source': 'gocomics-political'},
            {'slug': 'nick-anderson', 'source': 'tinyview'},
            {'slug': 'calvin-hobbes', 'source': 'gocomics'}  # Legacy
        ]
        
        for comic in comic_configs:
            scraper = ScraperFactory.get_scraper_for_comic(comic)
            
            # Should return appropriate scraper
            assert scraper is not None
            
            # Source should match (with gocomics -> gocomics-daily conversion)
            expected_source = comic['source']
            if expected_source == 'gocomics':
                expected_source = 'gocomics-daily'
            
            assert scraper.get_source_name() == expected_source
    
    def test_factory_error_handling(self):
        """Test factory error handling for edge cases."""
        from comiccaster.scraper_factory import ScraperFactory
        
        # Test None source
        with pytest.raises(ValueError):
            ScraperFactory.get_scraper(None)
        
        # Test empty string
        with pytest.raises(ValueError):
            ScraperFactory.get_scraper('')
        
        # Test whitespace
        with pytest.raises(ValueError):
            ScraperFactory.get_scraper('   ')
    
    def test_factory_performance_with_many_requests(self):
        """Test factory performance with many scraper requests."""
        from comiccaster.scraper_factory import ScraperFactory
        import time
        
        # Clear cache first
        ScraperFactory.clear_cache()
        
        start_time = time.time()
        
        # Request many scrapers
        for _ in range(100):
            scraper = ScraperFactory.get_scraper('gocomics-daily')
            assert scraper is not None
        
        end_time = time.time()
        
        # Should be fast due to caching (less than 1 second for 100 requests)
        assert (end_time - start_time) < 1.0