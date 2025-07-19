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
        
        comic_data = {
            'title': 'Garfield - 2025-01-19',
            'url': 'https://www.gocomics.com/garfield/2025/01/19',
            'images': [
                {'url': 'https://assets.amuniversal.com/garfield.jpg', 'alt': 'Garfield comic'}
            ],
            'published_date': datetime(2025, 1, 19, tzinfo=timezone.utc),
            'description': 'Daily Garfield comic'
        }
        
        entry = generator.create_entry(comic_data)
        
        # Should work exactly as before for single images
        assert entry is not None
        content = entry.content()
        assert 'garfield.jpg' in content
        assert 'img src=' in content
    
    def test_generate_multi_image_entry(self):
        """Test RSS entry generation for multi-image comic."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_data = {
            'title': 'ADHDinos - Multi Panel Comic',
            'url': 'https://tinyview.com/adhdinos/2025/01/15/test',
            'images': [
                {'url': 'https://cdn.tinyview.com/panel1.jpg', 'alt': 'Panel 1'},
                {'url': 'https://cdn.tinyview.com/panel2.jpg', 'alt': 'Panel 2'},
                {'url': 'https://cdn.tinyview.com/panel3.jpg', 'alt': 'Panel 3'}
            ],
            'published_date': datetime(2025, 1, 15, tzinfo=timezone.utc),
            'description': 'Multi-panel comic from Tinyview'
        }
        
        entry = generator.create_entry(comic_data)
        
        # Should contain all three images
        assert entry is not None
        content = entry.content()
        assert 'panel1.jpg' in content
        assert 'panel2.jpg' in content
        assert 'panel3.jpg' in content
        
        # Images should be in correct order
        panel1_pos = content.find('panel1.jpg')
        panel2_pos = content.find('panel2.jpg')
        panel3_pos = content.find('panel3.jpg')
        
        assert panel1_pos < panel2_pos < panel3_pos
    
    def test_multi_image_html_structure(self):
        """Test that multi-image entries have proper HTML structure."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_data = {
            'title': 'Test Multi-Panel Comic',
            'url': 'https://example.com/test',
            'images': [
                {'url': 'https://example.com/1.jpg', 'alt': 'Panel 1', 'title': 'First panel'},
                {'url': 'https://example.com/2.jpg', 'alt': 'Panel 2'}
            ],
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_data)
        content = entry.content()
        
        # Should have proper image container structure
        assert '<div class="comic-gallery">' in content or '<div class="comic-images">' in content
        
        # Each image should have proper attributes
        assert 'alt="Panel 1"' in content
        assert 'alt="Panel 2"' in content
        assert 'title="First panel"' in content
        
        # Should be mobile-friendly
        assert 'width="100%"' in content or 'max-width' in content or 'responsive' in content
    
    def test_image_loading_optimization(self):
        """Test that images are optimized for feed readers."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_data = {
            'title': 'Test Comic',
            'url': 'https://example.com/test',
            'images': [
                {'url': 'https://example.com/large-image.jpg', 'alt': 'Large image'}
            ],
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_data)
        content = entry.content()
        
        # Should have loading optimization attributes
        assert 'loading="lazy"' in content or 'data-src=' in content
        
        # Should have reasonable size constraints
        assert 'style=' in content  # CSS styling for size control
    
    def test_feed_entry_with_description_and_images(self):
        """Test feed entry includes both description text and images."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_data = {
            'title': 'Test Comic with Description',
            'url': 'https://example.com/test',
            'description': 'This is a test comic with a description.',
            'images': [
                {'url': 'https://example.com/comic.jpg', 'alt': 'Comic panel'}
            ],
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_data)
        content = entry.content()
        
        # Should contain both description and image
        assert 'This is a test comic with a description.' in content
        assert 'comic.jpg' in content
        assert '<img' in content
    
    def test_feed_validation_with_multi_images(self):
        """Test that feeds with multi-image entries are valid RSS."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        # Create feed
        comic_info = {
            'name': 'Test Multi-Image Comic',
            'slug': 'test-multi',
            'source': 'tinyview',
            'author': 'Test Author',
            'url': 'https://example.com/test-multi'
        }
        
        feed = generator.create_feed(comic_info)
        
        # Add multi-image entry
        comic_data = {
            'title': 'Multi-Image Test Entry',
            'url': 'https://example.com/test-multi/entry',
            'images': [
                {'url': 'https://example.com/1.jpg', 'alt': 'Panel 1'},
                {'url': 'https://example.com/2.jpg', 'alt': 'Panel 2'}
            ],
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_data)
        feed.add_entry(entry)
        
        # Generate RSS and check it's valid XML
        rss_content = feed.rss_str(pretty=True)
        
        # Should be valid XML (no parsing errors)
        assert b'<?xml version=' in rss_content
        assert b'<rss version="2.0"' in rss_content
        assert b'<item>' in rss_content
        assert b'</item>' in rss_content
        
        # Should contain image content
        assert b'1.jpg' in rss_content
        assert b'2.jpg' in rss_content
    
    def test_backward_compatibility_single_image(self):
        """Test that single-image comics still work exactly as before."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        # Test with old-style single image data
        old_style_data = {
            'title': 'Old Style Comic',
            'url': 'https://example.com/old',
            'image': 'https://example.com/old-comic.jpg',  # Old single image field
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(old_style_data)
        content = entry.content()
        
        # Should still work
        assert 'old-comic.jpg' in content
        assert '<img' in content
    
    def test_empty_images_handling(self):
        """Test handling of entries with no images."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_data = {
            'title': 'Text Only Entry',
            'url': 'https://example.com/text-only',
            'description': 'This entry has no images.',
            'images': [],  # No images
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_data)
        
        # Should create entry successfully
        assert entry is not None
        
        content = entry.content()
        # Should have description but no img tags
        assert 'This entry has no images.' in content
        assert '<img' not in content
    
    def test_image_alt_text_accessibility(self):
        """Test that all images have proper alt text for accessibility."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_data = {
            'title': 'Accessibility Test',
            'url': 'https://example.com/accessibility',
            'images': [
                {'url': 'https://example.com/1.jpg', 'alt': 'Panel 1: Setup'},
                {'url': 'https://example.com/2.jpg', 'alt': 'Panel 2: Punchline'},
                {'url': 'https://example.com/3.jpg'}  # Missing alt text
            ],
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_data)
        content = entry.content()
        
        # Should have alt text for first two images
        assert 'alt="Panel 1: Setup"' in content
        assert 'alt="Panel 2: Punchline"' in content
        
        # Should provide fallback alt text for image without alt
        assert 'alt=' in content  # Some alt text should be present for all images
    
    def test_image_gallery_responsive_design(self):
        """Test that image galleries are responsive and mobile-friendly."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        comic_data = {
            'title': 'Responsive Gallery Test',
            'url': 'https://example.com/responsive',
            'images': [
                {'url': 'https://example.com/wide.jpg', 'alt': 'Wide panel'},
                {'url': 'https://example.com/tall.jpg', 'alt': 'Tall panel'},
                {'url': 'https://example.com/square.jpg', 'alt': 'Square panel'}
            ],
            'published_date': datetime.now(timezone.utc)
        }
        
        entry = generator.create_entry(comic_data)
        content = entry.content()
        
        # Should have responsive CSS
        responsive_indicators = [
            'max-width: 100%',
            'width: 100%',
            'responsive',
            'flex',
            'display: block'
        ]
        
        # At least one responsive indicator should be present
        assert any(indicator in content for indicator in responsive_indicators)
        
        # Should have proper image spacing
        spacing_indicators = [
            'margin',
            'padding',
            'gap',
            'space'
        ]
        
        # Should have some spacing control
        assert any(indicator in content for indicator in spacing_indicators)
    
    def test_performance_with_many_images(self):
        """Test performance with comics that have many images."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        # Create comic with many panels (like a webtoon)
        many_images = [
            {'url': f'https://example.com/panel{i}.jpg', 'alt': f'Panel {i}'}
            for i in range(1, 21)  # 20 images
        ]
        
        comic_data = {
            'title': 'Many Panel Comic',
            'url': 'https://example.com/many-panels',
            'images': many_images,
            'published_date': datetime.now(timezone.utc)
        }
        
        import time
        start_time = time.time()
        
        entry = generator.create_entry(comic_data)
        
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second)
        assert (end_time - start_time) < 1.0
        
        # Should contain all images
        content = entry.content()
        assert content.count('<img') == 20
    
    def test_integration_with_tinyview_scraper_output(self):
        """Test integration with actual Tinyview scraper output format."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        # Simulate data from TinyviewScraper
        tinyview_data = {
            'slug': 'adhdinos',
            'date': '2025/01/15',
            'source': 'tinyview',
            'title': 'ADHDinos - Daily Struggles',
            'url': 'https://tinyview.com/adhdinos/2025/01/15/daily-struggles',
            'images': [
                {
                    'url': 'https://cdn.tinyview.com/adhdinos/2025-01-15-1.jpg',
                    'alt': 'Panel 1: Setup',
                    'title': 'The beginning of the struggle'
                },
                {
                    'url': 'https://cdn.tinyview.com/adhdinos/2025-01-15-2.jpg',
                    'alt': 'Panel 2: Conflict',
                    'title': 'The struggle intensifies'
                },
                {
                    'url': 'https://cdn.tinyview.com/adhdinos/2025-01-15-3.jpg',
                    'alt': 'Panel 3: Resolution',
                    'title': 'Finding a solution'
                }
            ],
            'image_count': 3,
            'published_date': datetime(2025, 1, 15, tzinfo=timezone.utc)
        }
        
        entry = generator.create_entry(tinyview_data)
        
        # Should handle Tinyview format correctly
        assert entry is not None
        content = entry.content()
        
        # Should contain all Tinyview images
        assert 'adhdinos/2025-01-15-1.jpg' in content
        assert 'adhdinos/2025-01-15-2.jpg' in content
        assert 'adhdinos/2025-01-15-3.jpg' in content
        
        # Should preserve alt text and titles
        assert 'Panel 1: Setup' in content
        assert 'Panel 2: Conflict' in content
        assert 'Panel 3: Resolution' in content