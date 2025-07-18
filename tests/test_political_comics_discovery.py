"""
Test suite for political comics discovery functionality.
Following TDD principles - these tests are written before implementation.
"""

import pytest
import json
from unittest.mock import Mock, patch, mock_open
from pathlib import Path


class TestPoliticalComicsDiscovery:
    """Test cases for discovering political comics from GoComics."""
    
    @pytest.fixture
    def mock_political_comics_html(self):
        """Mock HTML response from political comics A-Z page."""
        return """
        <html>
        <body>
            <div class="gc-blended-link">
                <a href="/algoodwyn">Al Goodwyn</a>
            </div>
            <div class="gc-blended-link">
                <a href="/bill-bramhall">Bill Bramhall</a>
            </div>
            <div class="gc-blended-link">
                <a href="/clayjones">Clay Jones</a>
            </div>
        </body>
        </html>
        """
    
    @pytest.fixture
    def expected_comics_list(self):
        """Expected output format for political comics list."""
        return [
            {
                "name": "Al Goodwyn",
                "slug": "algoodwyn",
                "url": "https://www.gocomics.com/algoodwyn",
                "author": "Al Goodwyn",
                "position": 1,
                "is_political": True,
                "publishing_frequency": None  # To be determined by analyzer
            },
            {
                "name": "Bill Bramhall", 
                "slug": "bill-bramhall",
                "url": "https://www.gocomics.com/bill-bramhall",
                "author": "Bill Bramhall",
                "position": 2,
                "is_political": True,
                "publishing_frequency": None
            },
            {
                "name": "Clay Jones",
                "slug": "clayjones", 
                "url": "https://www.gocomics.com/clayjones",
                "author": "Clay Jones",
                "position": 3,
                "is_political": True,
                "publishing_frequency": None
            }
        ]
    
    def test_fetch_political_comics_list(self, mock_political_comics_html):
        """Test fetching the A-Z political comics list from GoComics."""
        # This test will fail until we implement discover_political_comics module
        from scripts.discover_political_comics import PoliticalComicsDiscoverer
        
        with patch('comiccaster.http_client.requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.text = mock_political_comics_html
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            discoverer = PoliticalComicsDiscoverer()
            comics = discoverer.fetch_comics_list()
            
            assert len(comics) == 3
            assert comics[0]['name'] == 'Al Goodwyn'
            assert comics[0]['slug'] == 'algoodwyn'
            assert comics[0]['is_political'] == True
    
    def test_extract_comic_metadata(self):
        """Test extracting name, author, slug from HTML elements."""
        from scripts.discover_political_comics import PoliticalComicsDiscoverer
        
        html_snippet = '<a href="/test-comic">Test Comic Name</a>'
        discoverer = PoliticalComicsDiscoverer()
        
        metadata = discoverer.extract_comic_metadata(html_snippet, position=1)
        
        assert metadata['name'] == 'Test Comic Name'
        assert metadata['slug'] == 'test-comic'
        assert metadata['url'] == 'https://www.gocomics.com/test-comic'
        assert metadata['author'] == 'Test Comic Name'  # Default to name if author not specified
        assert metadata['position'] == 1
        assert metadata['is_political'] == True
    
    def test_handle_discovery_errors(self):
        """Test error handling for network/parsing failures."""
        from scripts.discover_political_comics import PoliticalComicsDiscoverer
        
        with patch('comiccaster.http_client.requests.Session.get') as mock_get:
            # Test network error
            mock_get.side_effect = Exception("Network error")
            
            discoverer = PoliticalComicsDiscoverer()
            comics = discoverer.fetch_comics_list()
            
            assert comics == []  # Should return empty list on error
    
    def test_save_political_comics_list(self, expected_comics_list, tmp_path):
        """Test saving discovered comics to JSON file."""
        from scripts.discover_political_comics import PoliticalComicsDiscoverer
        
        discoverer = PoliticalComicsDiscoverer()
        output_file = tmp_path / "political_comics_list.json"
        
        discoverer.save_comics_list(expected_comics_list, output_file)
        
        assert output_file.exists()
        
        with open(output_file) as f:
            saved_data = json.load(f)
        
        assert len(saved_data) == 3
        assert saved_data[0]['name'] == 'Al Goodwyn'
        assert saved_data[0]['is_political'] == True
    
    def test_validate_comic_url(self):
        """Test URL validation for discovered comics."""
        from scripts.discover_political_comics import PoliticalComicsDiscoverer
        
        discoverer = PoliticalComicsDiscoverer()
        
        # Valid URLs
        assert discoverer.validate_url("/algoodwyn") == True
        assert discoverer.validate_url("/bill-bramhall") == True
        assert discoverer.validate_url("/clay-jones-2") == True
        
        # Invalid URLs
        assert discoverer.validate_url("") == False
        assert discoverer.validate_url("#") == False
        assert discoverer.validate_url("javascript:void(0)") == False
        assert discoverer.validate_url("http://external.com/comic") == False
    
    def test_deduplicate_comics(self):
        """Test removing duplicate comics from discovery results."""
        from scripts.discover_political_comics import PoliticalComicsDiscoverer
        
        comics_with_dupes = [
            {"name": "Al Goodwyn", "slug": "algoodwyn"},
            {"name": "Al Goodwyn", "slug": "algoodwyn"},  # Duplicate
            {"name": "Bill Bramhall", "slug": "bill-bramhall"}
        ]
        
        discoverer = PoliticalComicsDiscoverer()
        deduped = discoverer.deduplicate_comics(comics_with_dupes)
        
        assert len(deduped) == 2
        assert deduped[0]['slug'] == 'algoodwyn'
        assert deduped[1]['slug'] == 'bill-bramhall'
    
    @pytest.mark.network
    def test_integration_fetch_real_political_comics(self):
        """Integration test - actually fetch from GoComics (marked for network tests)."""
        from scripts.discover_political_comics import PoliticalComicsDiscoverer
        
        discoverer = PoliticalComicsDiscoverer()
        comics = discoverer.fetch_comics_list()
        
        # Should discover 60+ political comics
        assert len(comics) > 60
        
        # Check some known political cartoonists exist
        comic_slugs = [comic['slug'] for comic in comics]
        assert 'algoodwyn' in comic_slugs
        assert 'lisabenson' in comic_slugs
        assert 'mattwuerker' in comic_slugs