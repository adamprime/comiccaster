"""
Test suite for Epic 2: Tinyview Scraper Implementation.
Following TDD principles - these tests are written before implementation enhancements.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from selenium.common.exceptions import TimeoutException


class TestTinyviewScraperStory21:
    """Test cases for Story 2.1: Basic Tinyview Scraper for Single Images."""
    
    def test_scraper_inherits_from_base_scraper(self):
        """Test that TinyviewScraper inherits from BaseScraper."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        from comiccaster.base_scraper import BaseScraper
        
        scraper = TinyviewScraper()
        assert isinstance(scraper, BaseScraper)
        assert scraper.get_source_name() == "tinyview"
    
    def test_tinyview_url_construction(self):
        """Test that Tinyview URLs are constructed correctly."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Test URL construction logic (this tests the internal fetch_comic_page method)
        comic_slug = 'nick-anderson'
        date = '2025/01/17'
        
        # The implementation first goes to the main comic page
        expected_main_url = f"https://tinyview.com/{comic_slug}"
        
        # We'll verify this by mocking the driver and checking the URL passed to get()
        with patch.object(scraper, 'setup_driver'), \
             patch.object(scraper, 'driver') as mock_driver:
            
            # Mock the main page to have no date links
            mock_driver.page_source = '<html><body>No strips for this date</body></html>'
            scraper.fetch_comic_page(comic_slug, date)
            
            # Check that driver.get was called with main comic URL first
            mock_driver.get.assert_called()
            called_url = mock_driver.get.call_args[0][0]
            assert called_url == expected_main_url
    
    @pytest.mark.network
    def test_scrape_single_image_comic_with_mock(self):
        """Test scraping single image Tinyview comic with mocked Selenium."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        # Mock HTML content with single CDN image
        # Using actual TinyView URL format
        mock_html = '''
        <html>
            <head><title>Nick Anderson - Jan 17, 2025</title></head>
            <body>
                <div class="comic-container">
                    <img src="https://cdn.tinyview.com/nick-anderson/2025/01/17/federal-overreach/nick-anderson-cartoon.jpg" 
                         alt="Nick Anderson cartoon" 
                         title="Political cartoon">
                </div>
            </body>
        </html>
        '''
        
        scraper = TinyviewScraper()
        
        # Mock return value should be (html, url) tuple
        mock_url = 'https://tinyview.com/nick-anderson/2025/01/17/federal-overreach'
        with patch.object(scraper, 'fetch_comic_page', return_value=(mock_html, mock_url)):
            result = scraper.scrape_comic('nick-anderson', '2025/01/17')
            
            # Verify result structure
            assert result is not None
            assert 'images' in result
            assert len(result['images']) == 1
            assert result['image_count'] == 1
            
            # Verify image data
            image = result['images'][0]
            assert image['url'].startswith('https://cdn.tinyview.com/')
            assert image['alt'] == 'Nick Anderson cartoon'
            assert image['title'] == 'Political cartoon'
            
            # Verify comic data structure
            assert result['source'] == 'tinyview'
            assert result['comic_slug'] == 'nick-anderson'
            assert result['date'] == '2025/01/17'
    
    def test_cdn_image_detection_logic(self):
        """Test that CDN images are correctly detected and extracted."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Test HTML with various image sources - only CDN should be extracted
        test_html = '''
        <html>
            <body>
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip-title/valid-comic.jpg" alt="Valid comic">
                <img src="https://example.com/invalid.jpg" alt="Invalid source">
                <img src="/local/path.jpg" alt="Local path">
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip-title/another-valid.jpg" alt="Another valid">
            </body>
        </html>
        '''
        
        images = scraper.extract_images(test_html, 'test-comic', '2025/01/17')
        
        # Should only extract CDN images
        assert len(images) == 2
        assert all(img['url'].startswith('https://cdn.tinyview.com/') for img in images)
        assert 'valid-comic.jpg' in images[0]['url']
        assert 'another-valid.jpg' in images[1]['url']
    
    def test_lazy_loading_image_detection(self):
        """Test detection of images using data-src attribute (lazy loading)."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Test HTML with lazy-loaded images
        test_html = '''
        <html>
            <body>
                <img data-src="https://cdn.tinyview.com/lazy-comic.jpg" 
                     src="placeholder.jpg" 
                     alt="Lazy loaded comic">
                <img data-src="https://tinyview.com/another-lazy.jpg" 
                     alt="Another lazy image">
            </body>
        </html>
        '''
        
        images = scraper.extract_images(test_html, 'test-comic', '2025/01/17')
        
        # Should detect lazy-loaded images from Tinyview domains
        assert len(images) >= 1
        found_urls = [img['url'] for img in images]
        assert any('lazy-comic.jpg' in url for url in found_urls)
    
    def test_angular_page_loading_handling(self):
        """Test that scraper handles Angular page loading delays."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        from datetime import datetime
        
        scraper = TinyviewScraper()
        
        # The new implementation uses get_recent_comics, so let's test that directly
        # Mock setup_driver to set the driver
        def mock_setup_driver():
            scraper.driver = mock_driver
        
        with patch.object(scraper, 'setup_driver', side_effect=mock_setup_driver), \
             patch('time.sleep') as mock_sleep:
            
            # Create mock driver
            mock_driver = Mock()
            
            # Use today's date to ensure comics are within the date range
            today = datetime.now()
            yesterday = today.replace(day=today.day-1)
            
            # Main page with comic links using dates within range
            main_page_html = f'''<html>
                <body>
                    <a href="/test-comic/{today.year:04d}/{today.month:02d}/{today.day:02d}/strip-title">Comic for Today</a>
                    <a href="/test-comic/{yesterday.year:04d}/{yesterday.month:02d}/{yesterday.day:02d}/other-strip">Comic for Yesterday</a>
                </body>
            </html>'''
            
            mock_driver.page_source = main_page_html
            mock_driver.title = 'Test Comic'
            
            # Make driver.get not raise errors
            mock_driver.get.return_value = None
            
            # Test get_recent_comics which is what the new implementation uses
            recent_comics = scraper.get_recent_comics('test-comic', days_back=30)
            
            # Verify that sleep was called for page loading
            assert mock_sleep.called
            assert mock_sleep.call_count >= 1
            
            # Should find comics in the page
            assert len(recent_comics) > 0
            assert any(f'{today.year:04d}/{today.month:02d}/{today.day:02d}' in comic['date'] for comic in recent_comics)
    
    def test_metadata_extraction(self):
        """Test extraction of comic metadata from HTML."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        test_html = '''
        <html>
            <head>
                <title>Nick Anderson - Political Cartoon - Jan 17, 2025</title>
                <meta property="og:title" content="Nick Anderson Cartoon">
                <meta property="og:description" content="Daily political cartoon">
            </head>
            <body>
                <img src="https://cdn.tinyview.com/test.jpg" alt="Test">
            </body>
        </html>
        '''
        
        metadata = scraper.extract_metadata(test_html, 'nick-anderson', '2025/01/17')
        
        assert metadata['comic_slug'] == 'nick-anderson'
        assert metadata['date'] == '2025/01/17'
        assert 'Nick Anderson Cartoon' in metadata['title']
        assert metadata['description'] == 'Daily political cartoon'
        assert isinstance(metadata['published_date'], datetime)
    
    def test_selenium_driver_setup(self):
        """Test that Selenium WebDriver is properly configured."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Test Chrome first (new default), then Firefox fallback
        with patch('comiccaster.tinyview_scraper.webdriver.Chrome') as mock_chrome, \
             patch('comiccaster.tinyview_scraper.webdriver.Firefox') as mock_firefox:
            mock_driver = Mock()
            mock_chrome.return_value = mock_driver
            
            scraper.setup_driver()
            
            # Verify Chrome WebDriver was tried first
            mock_chrome.assert_called_once()
            
            # Verify headless configuration for Chrome
            options_arg = mock_chrome.call_args[1]['options']
            assert any('--headless' in str(arg) for arg in options_arg.arguments)
            
            # Verify window size is set
            mock_driver.set_window_size.assert_called_with(1920, 1080)
            
            # Verify driver is stored
            assert scraper.driver == mock_driver
    
    def test_driver_cleanup(self):
        """Test that WebDriver is properly cleaned up."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        mock_driver = Mock()
        scraper.driver = mock_driver
        
        scraper.close_driver()
        
        # Verify driver.quit() was called
        mock_driver.quit.assert_called_once()
        
        # Verify driver reference is cleared
        assert scraper.driver is None
    
    def test_standardized_output_format(self):
        """Test that scraper returns standardized comic data structure."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        mock_html = '''
        <html>
            <head><title>Test Comic</title></head>
            <body>
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip-title/test.jpg" alt="Test comic">
            </body>
        </html>
        '''
        
        # Mock return value should be (html, url) tuple
        mock_url = 'https://tinyview.com/test-comic/2025/01/17/strip-title'
        with patch.object(scraper, 'fetch_comic_page', return_value=(mock_html, mock_url)):
            result = scraper.scrape_comic('test-comic', '2025/01/17')
            
            # Verify standardized output structure
            required_fields = [
                'source', 'comic_slug', 'date', 'title', 'url', 
                'images', 'image_count', 'published_date'
            ]
            
            for field in required_fields:
                assert field in result, f"Missing required field: {field}"
            
            # Verify data types
            assert isinstance(result['images'], list)
            assert isinstance(result['image_count'], int)
            assert result['source'] == 'tinyview'
            
            # Verify image structure
            if result['images']:
                image = result['images'][0]
                assert 'url' in image
                assert 'alt' in image
                assert 'title' in image


class TestTinyviewScraperStory22:
    """Test cases for Story 2.2: Multi-Image Comic Support."""
    
    @pytest.mark.network
    def test_scrape_multi_image_comic_with_mock(self):
        """Test scraping multi-image Tinyview comic."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        # Mock HTML content with multiple CDN images
        mock_html = '''
        <html>
            <head><title>ADHDinos - Multi Panel Comic</title></head>
            <body>
                <div class="comic-panels">
                    <img src="https://cdn.tinyview.com/adhdinos/2025/01/15/multi-panel/panel-1.jpg" alt="Panel 1">
                    <img src="https://cdn.tinyview.com/adhdinos/2025/01/15/multi-panel/panel-2.jpg" alt="Panel 2">
                    <img src="https://cdn.tinyview.com/adhdinos/2025/01/15/multi-panel/panel-3.jpg" alt="Panel 3">
                </div>
            </body>
        </html>
        '''
        
        scraper = TinyviewScraper()
        
        # Mock return value should be (html, url) tuple
        mock_url = 'https://tinyview.com/adhdinos/2025/01/15/multi-panel'
        with patch.object(scraper, 'fetch_comic_page', return_value=(mock_html, mock_url)):
            result = scraper.scrape_comic('adhdinos', '2025/01/15')
            
            # Verify multi-image result
            assert result is not None
            assert result['image_count'] == 3
            assert len(result['images']) == 3
            
            # Verify all images are from CDN
            assert all(img['url'].startswith('https://cdn.tinyview.com/') for img in result['images'])
            
            # Verify image ordering is preserved
            urls = [img['url'] for img in result['images']]
            assert 'panel-1.jpg' in urls[0]
            assert 'panel-2.jpg' in urls[1] 
            assert 'panel-3.jpg' in urls[2]
    
    def test_image_order_preservation(self):
        """Test that image order is preserved during extraction."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # HTML with images in specific order
        test_html = '''
        <html>
            <body>
                <div class="comic-container">
                    <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/panel-3.jpg" alt="Third panel">
                    <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/panel-1.jpg" alt="First panel">
                    <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/panel-2.jpg" alt="Second panel">
                </div>
            </body>
        </html>
        '''
        
        images = scraper.extract_images(test_html, 'test-comic', '2025/01/17')
        
        # Images should be in DOM order, not filename order
        assert len(images) == 3
        assert 'panel-3.jpg' in images[0]['url']  # First in DOM
        assert 'panel-1.jpg' in images[1]['url']  # Second in DOM
        assert 'panel-2.jpg' in images[2]['url']  # Third in DOM
        
        # Alt text should match
        assert images[0]['alt'] == 'Third panel'
        assert images[1]['alt'] == 'First panel'
        assert images[2]['alt'] == 'Second panel'
    
    def test_various_gallery_layouts(self):
        """Test handling of various comic gallery layouts."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Test different container patterns
        gallery_layouts = [
            # Layout 1: Direct div with images
            '''
            <div class="comic-strip">
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/layout1/image-1.jpg" alt="Panel 1">
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/layout1/image-2.jpg" alt="Panel 2">
            </div>
            ''',
            
            # Layout 2: Nested structure
            '''
            <div class="story-container">
                <div class="panel-wrapper">
                    <img src="https://cdn.tinyview.com/test-comic/2025/01/17/layout2/panel-a.jpg" alt="Panel A">
                </div>
                <div class="panel-wrapper">
                    <img src="https://cdn.tinyview.com/test-comic/2025/01/17/layout2/panel-b.jpg" alt="Panel B">
                </div>
            </div>
            ''',
            
            # Layout 3: Figure elements
            '''
            <article>
                <figure>
                    <img src="https://cdn.tinyview.com/test-comic/2025/01/17/layout3/figure-1.jpg" alt="Figure 1">
                </figure>
                <figure>
                    <img src="https://cdn.tinyview.com/test-comic/2025/01/17/layout3/figure-2.jpg" alt="Figure 2">
                </figure>
            </article>
            '''
        ]
        
        for i, layout_html in enumerate(gallery_layouts):
            images = scraper.extract_images(layout_html, 'test-comic', '2025/01/17')
            
            # Each layout should extract exactly 2 images
            assert len(images) == 2, f"Layout {i+1} failed: found {len(images)} images"
            
            # All should be CDN images
            assert all(img['url'].startswith('https://cdn.tinyview.com/') for img in images)
    
    def test_mixed_image_sources_filtering(self):
        """Test that only Tinyview CDN images are extracted from mixed sources."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # HTML with mixed image sources
        mixed_html = '''
        <html>
            <body>
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip1/comic-1.jpg" alt="Valid comic 1">
                <img src="https://ads.example.com/banner.jpg" alt="Ad banner">
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip2/comic-2.jpg" alt="Valid comic 2">
                <img src="/static/logo.png" alt="Site logo">
                <img src="https://social.example.com/share.jpg" alt="Social share">
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip3/comic-3.jpg" alt="Valid comic 3">
            </body>
        </html>
        '''
        
        images = scraper.extract_images(mixed_html, 'test-comic', '2025/01/17')
        
        # Should only extract the 3 CDN images
        assert len(images) == 3
        assert all(img['url'].startswith('https://cdn.tinyview.com/') for img in images)
        
        # Verify correct images were extracted
        urls = [img['url'] for img in images]
        assert any('comic-1.jpg' in url for url in urls)
        assert any('comic-2.jpg' in url for url in urls)
        assert any('comic-3.jpg' in url for url in urls)
    
    def test_empty_alt_text_handling(self):
        """Test handling of images with missing or empty alt text."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        test_html = '''
        <html>
            <body>
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/no-alt.jpg">
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/empty-alt.jpg" alt="">
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/with-alt.jpg" alt="Has alt text">
            </body>
        </html>
        '''
        
        images = scraper.extract_images(test_html, 'test-comic', '2025/01/17')
        
        assert len(images) == 3
        
        # Check alt text handling
        assert images[0]['alt'] == ''  # Missing alt
        assert images[1]['alt'] == ''  # Empty alt
        assert images[2]['alt'] == 'Has alt text'  # Proper alt


class TestTinyviewScraperStory23:
    """Test cases for Story 2.3: Error Handling and Resilience."""
    
    def test_handle_missing_comic_404(self):
        """Test graceful handling of 404 pages (missing comics)."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Mock fetch_comic_page to return None (simulating 404)
        with patch.object(scraper, 'fetch_comic_page', return_value=None):
            result = scraper.scrape_comic('non-existent', '2025/01/17')
            
            # Should return None for missing comics
            assert result is None
    
    def test_handle_empty_page_content(self):
        """Test handling of pages with no comic images."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Empty page with no CDN images
        empty_html = '''
        <html>
            <head><title>Empty Page</title></head>
            <body>
                <p>No comic today</p>
                <img src="/static/placeholder.jpg" alt="Placeholder">
            </body>
        </html>
        '''
        
        # Mock return value should be (html, url) tuple
        mock_url = 'https://tinyview.com/test-comic/2025/01/17/empty'
        with patch.object(scraper, 'fetch_comic_page', return_value=(empty_html, mock_url)):
            result = scraper.scrape_comic('test-comic', '2025/01/17')
            
            # Should return None when no CDN images found
            assert result is None
    
    def test_retry_on_timeout_with_mock(self):
        """Test retry logic on Selenium timeout."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        from datetime import datetime
        
        scraper = TinyviewScraper()
        scraper.max_retries = 2
        
        # Test that retries work when TimeoutException is raised
        with patch('comiccaster.tinyview_scraper.webdriver.Chrome') as mock_chrome, \
             patch('comiccaster.tinyview_scraper.webdriver.Firefox') as mock_firefox, \
             patch('time.sleep'):
            
            # Create mock driver
            mock_driver = Mock()
            mock_chrome.return_value = mock_driver
            
            # Track get calls
            get_call_count = 0
            def get_side_effect(url):
                nonlocal get_call_count
                get_call_count += 1
                if get_call_count == 1:
                    raise TimeoutException("First attempt timeout")
                # On retry, provide page with comics
                # Use a date within the last 30 days to ensure it's included
                today = datetime.now()
                mock_driver.page_source = f'''<html><body>
                    <a href="/test-comic/{today.year:04d}/{today.month:02d}/{today.day:02d}/strip">Today's Comic</a>
                </body></html>'''
            
            mock_driver.get.side_effect = get_side_effect
            mock_driver.title = 'Test Comic'
            mock_driver.page_source = '<html><body></body></html>'  # Initial empty page
            mock_driver.quit = Mock()  # Mock quit method
            mock_driver.set_window_size = Mock()
            mock_driver.implicitly_wait = Mock()
            mock_driver.set_page_load_timeout = Mock()
            
            # Call get_recent_comics which handles retries
            recent_comics = scraper.get_recent_comics('test-comic', days_back=30)
            
            # Should succeed after retry
            assert len(recent_comics) > 0
            assert get_call_count >= 2  # At least one retry
    
    def test_selenium_exception_handling(self):
        """Test handling of various Selenium exceptions."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        from selenium.common.exceptions import WebDriverException
        
        scraper = TinyviewScraper()
        
        with patch.object(scraper, 'setup_driver'), \
             patch.object(scraper, 'driver') as mock_driver:
            
            # Simulate WebDriver exception
            mock_driver.get.side_effect = WebDriverException("Browser crashed")
            
            result = scraper.fetch_comic_page('test-comic', '2025/01/17')
            
            # Should return None on WebDriver exception
            assert result is None
    
    def test_malformed_html_handling(self):
        """Test handling of malformed HTML content."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        # Malformed HTML
        malformed_html = '''
        <html>
            <head><title>Malformed</title>
            <body>
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/test.jpg" alt="Test
                <div><span>Unclosed tags
                <img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/test2.jpg">
        '''
        
        # Should handle malformed HTML gracefully
        images = scraper.extract_images(malformed_html, 'test-comic', '2025/01/17')
        
        # BeautifulSoup should still extract images despite malformed HTML
        assert len(images) >= 1
        assert images[0]['url'].startswith('https://cdn.tinyview.com/')
    
    def test_network_timeout_handling(self):
        """Test handling of network timeouts during page loading."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        scraper.max_retries = 3
        
        # Test that all retries are exhausted on persistent timeouts
        # Track setup calls
        setup_count = 0
        def mock_setup_driver():
            nonlocal setup_count
            setup_count += 1
            scraper.driver = mock_driver
        
        # Mock close_driver to reset driver
        def mock_close_driver():
            if scraper.driver:
                scraper.driver.quit()
                scraper.driver = None
        
        with patch.object(scraper, 'setup_driver', side_effect=mock_setup_driver), \
             patch.object(scraper, 'close_driver', side_effect=mock_close_driver), \
             patch('time.sleep'):
            
            # Create mock driver
            mock_driver = Mock()
            mock_driver.quit = Mock()
            
            # Always raise timeout
            mock_driver.get.side_effect = TimeoutException("Network timeout")
            mock_driver.title = 'Test Comic'
            
            # Call get_recent_comics which should exhaust retries
            recent_comics = scraper.get_recent_comics('test-comic', days_back=15)
            
            # Should return empty list after all retries fail
            assert recent_comics == []
            # Should have tried max_retries times (setup_driver called for each retry)
            assert setup_count == scraper.max_retries
    
    def test_invalid_date_handling(self):
        """Test handling of invalid date formats."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        
        test_html = '<html><img src="https://cdn.tinyview.com/test.jpg"></html>'
        
        # Mock return value should be (html, url) tuple
        mock_url = 'https://tinyview.com/test-comic/2025/01/17/test'
        with patch.object(scraper, 'fetch_comic_page', return_value=(test_html, mock_url)):
            # Test various invalid date formats
            invalid_dates = ['invalid', '2025-13-45', '2025/13/45', '', None]
            
            for invalid_date in invalid_dates:
                try:
                    result = scraper.scrape_comic('test-comic', invalid_date)
                    # Should handle gracefully, either returning result with fallback date or None
                    if result:
                        assert 'date' in result
                except Exception as e:
                    # Should not raise unhandled exceptions
                    pytest.fail(f"Unhandled exception for date '{invalid_date}': {e}")
    
    def test_comprehensive_logging(self):
        """Test that appropriate log messages are generated."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        import logging
        
        scraper = TinyviewScraper()
        
        # Capture log messages
        with patch('comiccaster.tinyview_scraper.logger') as mock_logger:
            mock_html = '<html><img src="https://cdn.tinyview.com/test-comic/2025/01/17/strip/test.jpg"></html>'
            
            # Mock return value should be (html, url) tuple
            mock_url = 'https://tinyview.com/test-comic/2025/01/17/strip'
            with patch.object(scraper, 'fetch_comic_page', return_value=(mock_html, mock_url)):
                result = scraper.scrape_comic('test-comic', '2025/01/17')
                
                # Should log image findings
                assert any('Found comic image' in str(call) for call in mock_logger.info.call_args_list)
    
    def test_driver_cleanup_on_exception(self):
        """Test that WebDriver is cleaned up even when exceptions occur."""
        from comiccaster.tinyview_scraper import TinyviewScraper
        
        scraper = TinyviewScraper()
        mock_driver = Mock()
        scraper.driver = mock_driver
        
        # Simulate exception during scraping
        with patch.object(scraper, 'fetch_comic_page', side_effect=Exception("Test error")):
            try:
                scraper.scrape_comic('test-comic', '2025/01/17')
            except:
                pass
            
            # Clean up should still work
            scraper.close_driver()
            mock_driver.quit.assert_called_once()