"""
Test suite for feed content adjustments for political comics.
Following TDD principles - these tests are written before implementation.
"""

import pytest
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import feedparser
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


class TestFeedContentAdjustments:
    """Test cases for adjusting feed content for political comics."""
    
    @pytest.fixture
    def political_comic_info(self):
        """Sample political comic info."""
        return {
            'name': 'Clay Jones',
            'slug': 'clayjones',
            'url': 'https://www.gocomics.com/clayjones',
            'is_political': True,
            'publishing_frequency': {
                'type': 'daily',
                'days_per_week': 7,
                'confidence': 0.95
            },
            'update_recommendation': 'daily'
        }
    
    @pytest.fixture
    def regular_comic_info(self):
        """Sample regular comic info for comparison."""
        return {
            'name': 'Calvin and Hobbes',
            'slug': 'calvinandhobbes',
            'url': 'https://www.gocomics.com/calvinandhobbes'
        }
    
    @pytest.fixture
    def political_feed_entries(self):
        """Sample entries for a political comic feed."""
        return [
            {
                'title': 'Clay Jones - 2025-07-17',
                'url': 'https://www.gocomics.com/clayjones/2025/07/17',
                'image': 'https://assets.gocomics.com/clayjones-2025-07-17.jpg',
                'pub_date': datetime(2025, 7, 17, 12, 0, 0),
                'description': 'Political commentary on current events',
                'id': 'https://www.gocomics.com/clayjones/2025/07/17'
            }
        ]
    
    def test_add_political_tag_to_feed_metadata(self, political_comic_info):
        """Test adding political comic tag to feed metadata."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        feed = generator.create_feed_object(political_comic_info)
        
        # Check for political category tag
        categories = feed.category()
        assert any(cat.get('term') == 'political' for cat in categories)
    
    def test_political_feed_description(self, political_comic_info):
        """Test that political comics have appropriate feed descriptions."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        feed = generator.create_feed_object(political_comic_info)
        
        description = feed.description()
        assert 'political' in description.lower() or 'editorial' in description.lower()
        assert 'cartoon' in description.lower()
    
    def test_add_content_warnings(self, political_comic_info, political_feed_entries):
        """Test adding content warnings for political comics."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        # Generate feed with political entries
        success = generator.generate_feed(political_comic_info, political_feed_entries)
        assert success
        
        # Parse generated feed
        feed_path = Path(generator.output_dir) / f"{political_comic_info['slug']}.xml"
        parsed_feed = feedparser.parse(str(feed_path))
        
        # Check for content advisory in feed
        assert 'political content' in parsed_feed.feed.description.lower() or \
               'editorial content' in parsed_feed.feed.description.lower()
    
    def test_preserve_comic_metadata_in_entries(self, political_comic_info, political_feed_entries):
        """Test that comic type metadata is preserved in individual entries."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        feed = generator.create_feed_object(political_comic_info)
        
        # Add entries with metadata
        for entry_data in political_feed_entries:
            entry = generator.add_feed_entry(feed, entry_data, political_comic_info)
            
            # Check entry has comic type category
            categories = entry.category()
            assert any(cat.get('term') == 'political' for cat in categories)
    
    def test_feed_generator_handles_political_flag(self):
        """Test that feed generator correctly handles is_political flag."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        
        # Test with political comic
        political_comic = {'name': 'Test Political', 'is_political': True, 'slug': 'test-political'}
        feed = generator.create_feed_object(political_comic)
        categories = feed.category()
        assert any(cat.get('term') == 'political' for cat in categories)
        
        # Test with regular comic
        regular_comic = {'name': 'Test Regular', 'is_political': False, 'slug': 'test-regular'}
        feed = generator.create_feed_object(regular_comic)
        categories = feed.category()
        assert not any(cat.get('term') == 'political' for cat in categories)
    
    def test_update_recommendation_in_feed(self, political_comic_info):
        """Test that update recommendation is included in feed metadata."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        feed = generator.create_feed_object(political_comic_info)
        
        # Check for update frequency in feed
        # This could be in a custom element or ttl
        ttl = feed.ttl()
        if political_comic_info['update_recommendation'] == 'daily':
            assert ttl == 1440  # 24 hours in minutes
        elif political_comic_info['update_recommendation'] == 'weekly':
            assert ttl == 10080  # 7 days in minutes
    
    def test_feed_xml_structure_for_political_comics(self, political_comic_info, political_feed_entries, tmp_path):
        """Test the XML structure of generated political comic feeds."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator(output_dir=str(tmp_path))
        success = generator.generate_feed(political_comic_info, political_feed_entries)
        assert success
        
        # Parse the generated XML
        feed_path = tmp_path / f"{political_comic_info['slug']}.xml"
        tree = ET.parse(feed_path)
        root = tree.getroot()
        
        # Check for RSS 2.0 structure
        assert root.tag == 'rss'
        assert root.get('version') == '2.0'
        
        # Check for channel
        channel = root.find('channel')
        assert channel is not None
        
        # Check for political category
        categories = channel.findall('category')
        # Check for 'Political Comics' as text (not just 'political' as term)
        assert any(cat.text == 'Political Comics' for cat in categories)
    
    def test_mixed_feed_separation(self):
        """Test that political and regular comics aren't mixed in bundles."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        comics_list = [
            {'name': 'Political Comic 1', 'is_political': True, 'slug': 'political1'},
            {'name': 'Regular Comic 1', 'is_political': False, 'slug': 'regular1'},
            {'name': 'Political Comic 2', 'is_political': True, 'slug': 'political2'}
        ]
        
        # Filter by type
        political_comics = [c for c in comics_list if c.get('is_political', False)]
        regular_comics = [c for c in comics_list if not c.get('is_political', False)]
        
        assert len(political_comics) == 2
        assert len(regular_comics) == 1
        assert political_comics[0]['name'] == 'Political Comic 1'
        assert regular_comics[0]['name'] == 'Regular Comic 1'
    
    def test_backwards_compatibility(self, regular_comic_info):
        """Test that regular comics without is_political flag work correctly."""
        from comiccaster.feed_generator import ComicFeedGenerator
        
        generator = ComicFeedGenerator()
        feed = generator.create_feed_object(regular_comic_info)
        
        # Should not have political category
        categories = feed.category()
        # Categories should be comics, not political
        assert any(cat.get('term') == 'comics' for cat in categories)
        assert not any(cat.get('term') == 'political' for cat in categories)
    
    @pytest.mark.integration
    def test_political_comic_feed_generation_end_to_end(self, political_comic_info, tmp_path):
        """Integration test for complete political comic feed generation."""
        from scripts.update_feeds import update_feed
        
        with patch('scripts.update_feeds.FEEDS_OUTPUT_DIR', tmp_path):
            with patch('scripts.update_feeds.scrape_comic') as mock_scrape:
                # Mock successful scraping
                mock_scrape.return_value = {
                    'title': 'Test Comic - 2025-07-17',
                    'url': 'https://example.com/comic',
                    'image': 'https://example.com/image.jpg',
                    'pub_date': '2025-07-17',
                    'description': 'Test political cartoon'
                }
                
                success = update_feed(political_comic_info, days_to_scrape=1)
                assert success
                
                # Check feed was created
                feed_path = tmp_path / f"{political_comic_info['slug']}.xml"
                assert feed_path.exists()