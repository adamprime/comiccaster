"""
Test suite for the Abstract Base Scraper Class.
Following TDD principles - these tests are written before implementation.
"""

import pytest
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any


class TestBaseScraper:
    """Test cases for the abstract base scraper interface."""
    
    def test_base_scraper_interface(self):
        """Test that base scraper defines required methods."""
        from comiccaster.base_scraper import BaseScraper
        
        # Check that BaseScraper is an ABC (Abstract Base Class)
        assert issubclass(BaseScraper, ABC)
        
        # Check required abstract methods exist
        assert hasattr(BaseScraper, 'scrape_comic')
        assert hasattr(BaseScraper, 'fetch_comic_page')
        assert hasattr(BaseScraper, 'extract_images')
        assert hasattr(BaseScraper, 'get_source_name')
        
        # Check that these methods are abstract
        assert getattr(BaseScraper.scrape_comic, '__isabstractmethod__', False)
        assert getattr(BaseScraper.fetch_comic_page, '__isabstractmethod__', False)
        assert getattr(BaseScraper.extract_images, '__isabstractmethod__', False)
        assert getattr(BaseScraper.get_source_name, '__isabstractmethod__', False)
    
    def test_base_scraper_not_instantiable(self):
        """Test that base scraper cannot be instantiated directly."""
        from comiccaster.base_scraper import BaseScraper
        
        with pytest.raises(TypeError) as exc_info:
            scraper = BaseScraper()
        
        # Check that the error message mentions abstract methods
        assert "abstract" in str(exc_info.value).lower()
    
    def test_base_scraper_common_attributes(self):
        """Test that base scraper has common attributes."""
        from comiccaster.base_scraper import BaseScraper
        
        # Create a concrete implementation for testing
        class TestScraper(BaseScraper):
            def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
                return None
            
            def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
                return None
            
            def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
                return []
            
            def get_source_name(self) -> str:
                return "test"
        
        scraper = TestScraper()
        
        # Check initialization with optional parameters
        assert hasattr(scraper, 'base_url')
        assert hasattr(scraper, 'timeout')
        assert hasattr(scraper, 'max_retries')
    
    def test_base_scraper_standardized_output(self):
        """Test that scraper output follows standardized format."""
        from comiccaster.base_scraper import BaseScraper
        
        # Create a concrete implementation that returns proper data
        class TestScraper(BaseScraper):
            def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
                return {
                    'slug': comic_slug,
                    'date': date,
                    'source': self.get_source_name(),
                    'title': 'Test Comic',
                    'url': 'https://example.com/comic',
                    'images': [
                        {'url': 'https://example.com/image1.jpg', 'alt': 'Comic panel 1'}
                    ],
                    'image_count': 1,
                    'published_date': datetime(2025, 1, 19)
                }
            
            def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
                return "<html>test</html>"
            
            def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
                return [{'url': 'https://example.com/image1.jpg', 'alt': 'Comic panel 1'}]
            
            def get_source_name(self) -> str:
                return "test"
        
        scraper = TestScraper()
        result = scraper.scrape_comic('test-comic', '2025/01/19')
        
        # Verify standardized output format
        assert result is not None
        assert 'slug' in result
        assert 'date' in result
        assert 'source' in result
        assert 'title' in result
        assert 'url' in result
        assert 'images' in result
        assert 'image_count' in result
        assert isinstance(result['images'], list)
        assert result['image_count'] == len(result['images'])
    
    def test_base_scraper_single_vs_multi_image(self):
        """Test that base scraper properly handles single vs multi-image comics."""
        from comiccaster.base_scraper import BaseScraper
        
        class SingleImageScraper(BaseScraper):
            def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
                images = self.extract_images("", comic_slug, date)
                result = {
                    'slug': comic_slug,
                    'source': self.get_source_name(),
                    'images': images,
                    'image_count': len(images)
                }
                
                # Add convenience fields for single image
                if len(images) == 1:
                    result['image_url'] = images[0]['url']
                    result['image_alt'] = images[0].get('alt', '')
                
                return result
            
            def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
                return "<html>test</html>"
            
            def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
                return [{'url': 'https://example.com/single.jpg', 'alt': 'Single comic'}]
            
            def get_source_name(self) -> str:
                return "single-test"
        
        class MultiImageScraper(BaseScraper):
            def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
                images = self.extract_images("", comic_slug, date)
                result = {
                    'slug': comic_slug,
                    'source': self.get_source_name(),
                    'images': images,
                    'image_count': len(images)
                }
                
                # No convenience fields for multi-image
                if len(images) == 1:
                    result['image_url'] = images[0]['url']
                    result['image_alt'] = images[0].get('alt', '')
                
                return result
            
            def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
                return "<html>test</html>"
            
            def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
                return [
                    {'url': 'https://example.com/panel1.jpg', 'alt': 'Panel 1'},
                    {'url': 'https://example.com/panel2.jpg', 'alt': 'Panel 2'},
                    {'url': 'https://example.com/panel3.jpg', 'alt': 'Panel 3'}
                ]
            
            def get_source_name(self) -> str:
                return "multi-test"
        
        # Test single image comic
        single_scraper = SingleImageScraper()
        single_result = single_scraper.scrape_comic('single-comic', '2025/01/19')
        
        assert single_result['image_count'] == 1
        assert 'image_url' in single_result
        assert 'image_alt' in single_result
        assert single_result['image_url'] == 'https://example.com/single.jpg'
        
        # Test multi-image comic
        multi_scraper = MultiImageScraper()
        multi_result = multi_scraper.scrape_comic('multi-comic', '2025/01/19')
        
        assert multi_result['image_count'] == 3
        assert 'image_url' not in multi_result  # No convenience fields for multi-image
        assert len(multi_result['images']) == 3
    
    def test_base_scraper_error_handling(self):
        """Test that base scraper provides standard error handling."""
        from comiccaster.base_scraper import BaseScraper
        
        class ErrorScraper(BaseScraper):
            def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
                # Simulate error by returning None
                return None
            
            def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
                # Simulate network error
                return None
            
            def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
                # Return empty list on error
                return []
            
            def get_source_name(self) -> str:
                return "error-test"
        
        scraper = ErrorScraper()
        result = scraper.scrape_comic('error-comic', '2025/01/19')
        
        # Should return None on error
        assert result is None
    
    def test_base_scraper_supports_both_gocomics_and_tinyview(self):
        """Test that base scraper can be extended for both GoComics and Tinyview."""
        from comiccaster.base_scraper import BaseScraper
        
        # These classes simulate the actual implementations
        class GoComicsScraper(BaseScraper):
            def __init__(self):
                super().__init__(base_url="https://www.gocomics.com")
            
            def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
                return {'source': 'gocomics-daily', 'slug': comic_slug}
            
            def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
                return f"<html>GoComics page for {comic_slug}</html>"
            
            def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
                return [{'url': f'https://assets.gocomics.com/{comic_slug}.jpg'}]
            
            def get_source_name(self) -> str:
                return "gocomics-daily"
        
        class TinyviewScraper(BaseScraper):
            def __init__(self):
                super().__init__(base_url="https://tinyview.com")
            
            def scrape_comic(self, comic_slug: str, date: str) -> Optional[Dict[str, Any]]:
                return {'source': 'tinyview', 'slug': comic_slug}
            
            def fetch_comic_page(self, comic_slug: str, date: str) -> Optional[str]:
                return f"<html>Tinyview page for {comic_slug}</html>"
            
            def extract_images(self, html_content: str, comic_slug: str, date: str) -> List[Dict[str, str]]:
                return [{'url': f'https://cdn.tinyview.com/{comic_slug}.jpg'}]
            
            def get_source_name(self) -> str:
                return "tinyview"
        
        # Both scrapers should work with the same interface
        gocomics = GoComicsScraper()
        tinyview = TinyviewScraper()
        
        assert gocomics.get_source_name() == "gocomics-daily"
        assert tinyview.get_source_name() == "tinyview"
        
        # Both should have different base URLs
        assert gocomics.base_url == "https://www.gocomics.com"
        assert tinyview.base_url == "https://tinyview.com"