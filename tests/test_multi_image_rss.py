"""
Test suite for Story 1.4: Multi-Image RSS Feed Support.
Following TDD principles - these tests are written before implementation.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch


class TestMultiImageRSSSupport:
    """Test cases for multi-image RSS feed generation."""
    
    def test_generate_single_image_entry(self):
        """Test RSS entry generation for single-image comic (backward compatibility)."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Garfield',
            'slug': 'garfield',
            'author': 'Jim Davis'
        }
        
        metadata = {
            'title': 'Garfield - 2025-01-19',
            'url': 'https://www.gocomics.com/garfield/2025/01/19',
            'images': [
                {'url': 'https://assets.amuniversal.com/garfield.jpg', 'alt': 'Garfield comic'}
            ],
            'pub_date': datetime(2025, 1, 19, tzinfo=timezone.utc),
            'description': 'Daily Garfield comic'
        }
        
        entry = generator.create_entry(comic_info, metadata)
        
        # Should work exactly as before for single images
        assert entry is not None
        content = entry.content()
        # content() returns a dict with 'content' key
        content_str = content['content'] if isinstance(content, dict) else content
        assert 'garfield.jpg' in content_str
        assert 'img src=' in content_str
    
    def test_generate_multi_image_entry(self):
        """Test RSS entry generation for multi-image comic."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'ADHDinos',
            'slug': 'adhdinos',
            'author': 'Dani Donovan'
        }
        
        metadata = {
            'title': 'ADHDinos - Multi Panel Comic',
            'url': 'https://tinyview.com/adhdinos/2025/01/15/test',
            'images': [
                {'url': 'https://cdn.tinyview.com/panel1.jpg', 'alt': 'Panel 1'},
                {'url': 'https://cdn.tinyview.com/panel2.jpg', 'alt': 'Panel 2'},
                {'url': 'https://cdn.tinyview.com/panel3.jpg', 'alt': 'Panel 3'}
            ],
            'pub_date': datetime(2025, 1, 15, tzinfo=timezone.utc),
            'description': 'Multi-panel comic from Tinyview'
        }
        
        entry = generator.create_entry(comic_info, metadata)
        
        # Should contain all three images
        assert entry is not None
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        assert 'panel1.jpg' in content_str
        assert 'panel2.jpg' in content_str
        assert 'panel3.jpg' in content_str
        
        # Images should be in correct order
        panel1_pos = content_str.find('panel1.jpg')
        panel2_pos = content_str.find('panel2.jpg')
        panel3_pos = content_str.find('panel3.jpg')
        
        assert panel1_pos < panel2_pos < panel3_pos
    
    def test_multi_image_html_structure(self):
        """Test that multi-image entries have proper HTML structure."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Test Comic',
            'slug': 'test-comic'
        }
        
        metadata = {
            'title': 'Test Multi-Panel Comic',
            'url': 'https://example.com/test',
            'images': [
                {'url': 'https://example.com/1.jpg', 'alt': 'Panel 1', 'title': 'First panel'},
                {'url': 'https://example.com/2.jpg', 'alt': 'Panel 2'}
            ],
            'pub_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_info, metadata)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # Should have proper image container structure
        assert 'class="comic-gallery"' in content_str or 'class="comic-images"' in content_str
        
        # Each image should have proper attributes
        assert 'alt="Panel 1"' in content_str
        assert 'alt="Panel 2"' in content_str
        assert 'title="First panel"' in content_str
        
        # Should be mobile-friendly
        assert 'width="100%"' in content_str or 'max-width' in content_str or 'responsive' in content_str
    
    def test_image_loading_optimization(self):
        """Test that images are optimized for feed readers."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Test Comic',
            'slug': 'test-comic'
        }
        
        metadata = {
            'title': 'Test Comic',
            'url': 'https://example.com/test',
            'images': [
                {'url': 'https://example.com/large-image.jpg', 'alt': 'Large image'}
            ],
            'pub_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_info, metadata)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # Should have loading optimization attributes
        assert 'loading="lazy"' in content_str or 'data-src=' in content_str
        
        # Should have reasonable size constraints
        assert 'style=' in content_str  # CSS styling for size control
    
    def test_feed_validation_with_multi_images(self):
        """Test that feeds with multi-image entries validate correctly."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Test Comic',
            'slug': 'test-comic',
            'url': 'https://example.com/test-comic'
        }
        
        feed = generator.create_feed(comic_info)
        
        # Add multi-image entry
        metadata = {
            'title': 'Multi-Image Entry',
            'url': 'https://example.com/test/1',
            'images': [
                {'url': 'https://example.com/img1.jpg', 'alt': 'Image 1'},
                {'url': 'https://example.com/img2.jpg', 'alt': 'Image 2'}
            ],
            'pub_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_info, metadata)
        feed.add_entry(entry)
        
        # Generate RSS
        rss_content = feed.rss_str()
        
        # Basic validation
        assert rss_content is not None
        # Decode bytes to string for checking
        rss_str = rss_content.decode('utf-8')
        assert '<?xml' in rss_str
        assert '<rss' in rss_str
        assert 'img1.jpg' in rss_str
        assert 'img2.jpg' in rss_str
    
    def test_backward_compatibility_single_image(self):
        """Test that single-image comics still work with the new system."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Legacy Comic',
            'slug': 'legacy-comic'
        }
        
        # Single image data (as it would come from GoComics)
        metadata = {
            'title': 'Legacy Comic - 2025-01-19',
            'url': 'https://www.gocomics.com/legacy/2025/01/19',
            'images': [
                {'url': 'https://assets.amuniversal.com/legacy.jpg'}
            ],
            'pub_date': '2025-01-19'
        }
        
        entry = generator.create_entry(comic_info, metadata)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # Should work exactly as before
        assert entry is not None
        assert 'legacy.jpg' in content_str
        assert '<img' in content_str
        
        # Should not have gallery wrapper for single images
        assert 'comic-gallery' not in content_str or content_str.count('<img') == 1
    
    def test_empty_images_handling(self):
        """Test handling of entries with no images."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Test Comic',
            'slug': 'test-comic'
        }
        
        metadata = {
            'title': 'No Images Entry',
            'url': 'https://example.com/test',
            'images': [],
            'pub_date': datetime.now(timezone.utc),
            'description': 'This entry has no images'
        }
        
        entry = generator.create_entry(comic_info, metadata)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # Should handle gracefully
        assert entry is not None
        assert 'This entry has no images' in content_str
        assert '<img' not in content_str  # No images should be present
    
    def test_image_alt_text_accessibility(self):
        """Test that all images have proper alt text for accessibility."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Accessible Comic',
            'slug': 'accessible-comic'
        }
        
        metadata = {
            'title': 'Accessible Entry',
            'url': 'https://example.com/test',
            'images': [
                {'url': 'https://example.com/1.jpg', 'alt': 'Panel 1 description'},
                {'url': 'https://example.com/2.jpg'}  # No alt text provided
            ],
            'pub_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_info, metadata)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # First image should have provided alt text
        assert 'alt="Panel 1 description"' in content_str
        
        # Second image should have fallback alt text
        assert 'alt=' in content_str.replace('alt="Panel 1 description"', '')  # Check for second alt
    
    def test_image_gallery_responsive_design(self):
        """Test that multi-image galleries are responsive."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Responsive Comic',
            'slug': 'responsive-comic'
        }
        
        metadata = {
            'title': 'Responsive Gallery',
            'url': 'https://example.com/test',
            'images': [
                {'url': f'https://example.com/{i}.jpg', 'alt': f'Panel {i}'} 
                for i in range(1, 5)
            ],
            'pub_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_info, metadata)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # Should have responsive CSS
        assert 'max-width' in content_str or 'width: 100%' in content_str
        assert 'style=' in content_str
        
        # All images should be present
        for i in range(1, 5):
            assert f'{i}.jpg' in content_str
    
    def test_performance_with_many_images(self):
        """Test performance with comics that have many images."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'Long Comic',
            'slug': 'long-comic'
        }
        
        # Create a comic with 20 panels
        metadata = {
            'title': 'Long Multi-Panel Comic',
            'url': 'https://example.com/long',
            'images': [
                {'url': f'https://example.com/panel{i:02d}.jpg', 'alt': f'Panel {i}'} 
                for i in range(1, 21)
            ],
            'pub_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_info, metadata)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # All panels should be included
        assert all(f'panel{i:02d}.jpg' in content_str for i in range(1, 21))
        
        # Should maintain order
        positions = [content_str.find(f'panel{i:02d}.jpg') for i in range(1, 21)]
        assert positions == sorted(positions)
    
    def test_integration_with_tinyview_scraper_output(self):
        """Test that Tinyview scraper output integrates correctly."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_info = {
            'name': 'ADHDinos',
            'slug': 'adhdinos',
            'source': 'tinyview'
        }
        
        # Simulated Tinyview scraper output
        scraper_output = {
            'title': 'ADHDinos - 2025-01-15',
            'url': 'https://tinyview.com/adhdinos/2025/01/15/comic-title',
            'images': [
                {
                    'url': 'https://cdn.tinyview.com/adhdinos/2025-01-15-panel1.jpg',
                    'alt': 'ADHDinos comic panel 1',
                    'title': 'Panel 1 of 3'
                },
                {
                    'url': 'https://cdn.tinyview.com/adhdinos/2025-01-15-panel2.jpg',
                    'alt': 'ADHDinos comic panel 2',
                    'title': 'Panel 2 of 3'
                },
                {
                    'url': 'https://cdn.tinyview.com/adhdinos/2025-01-15-panel3.jpg',
                    'alt': 'ADHDinos comic panel 3',
                    'title': 'Panel 3 of 3'
                }
            ],
            'pub_date': datetime(2025, 1, 15, tzinfo=timezone.utc),
            'description': 'A multi-panel comic about ADHD experiences'
        }
        
        entry = generator.create_entry(comic_info, scraper_output)
        content = entry.content()
        content_str = content['content'] if isinstance(content, dict) else content
        
        # Should handle all panels
        assert all(f'panel{i}.jpg' in content_str for i in range(1, 4))
        
        # Should preserve alt text
        assert 'ADHDinos comic panel 1' in content_str
        assert 'ADHDinos comic panel 2' in content_str
        assert 'ADHDinos comic panel 3' in content_str