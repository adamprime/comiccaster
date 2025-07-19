"""Tests for the update_feeds.py script, particularly the regenerate_feed function."""

import pytest
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import tempfile
import shutil
import os
import sys

# Add the scripts directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.update_feeds import regenerate_feed, extract_image_from_description
from comiccaster.feed_generator import ComicFeedGenerator
import feedparser


@pytest.fixture
def temp_feed_dir():
    """Create a temporary directory for feeds."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def comic_info():
    """Sample comic information."""
    return {
        'name': 'Test Comic',
        'author': 'Test Author',
        'url': 'https://www.gocomics.com/test-comic',
        'slug': 'test-comic'
    }


def create_test_entries(count, start_date=None):
    """Create test feed entries with proper datetime objects."""
    if start_date is None:
        start_date = datetime.now(pytz.UTC) - timedelta(days=count)
    
    entries = []
    for i in range(count):
        date = start_date + timedelta(days=i)
        entries.append({
            'title': f'Test Comic - {date.strftime("%Y-%m-%d")}',
            'url': f'https://www.gocomics.com/test-comic/{date.strftime("%Y/%m/%d")}',
            'id': f'https://www.gocomics.com/test-comic/{date.strftime("%Y/%m/%d")}',
            'image_url': f'https://example.com/comic-{i}.jpg',
            'description': f'<img src="https://example.com/comic-{i}.jpg"> Comic for {date.strftime("%Y-%m-%d")}',
            'pub_date': date
        })
    return entries


class TestRegenerateFeed:
    """Test cases for the regenerate_feed function."""
    
    def test_regenerate_feed_under_limit(self, temp_feed_dir, comic_info, monkeypatch):
        """Test with fewer than 100 entries - all should be kept."""
        # Monkey patch the FEEDS_OUTPUT_DIR
        monkeypatch.setattr('scripts.update_feeds.FEEDS_OUTPUT_DIR', Path(temp_feed_dir))
        
        # Create an existing feed with 50 entries
        generator = ComicFeedGenerator(output_dir=str(temp_feed_dir))
        existing_entries = create_test_entries(50)
        generator.generate_feed(comic_info, existing_entries)
        
        # Create 3 new entries (more recent)
        newest_date = existing_entries[-1]['pub_date'] + timedelta(days=1)
        new_entries = create_test_entries(3, start_date=newest_date)
        
        # Run regenerate_feed
        result = regenerate_feed(comic_info, new_entries)
        
        assert result is True
        
        # Check the generated feed
        feed_path = Path(temp_feed_dir) / f"{comic_info['slug']}.xml"
        assert feed_path.exists()
        
        # Parse and verify
        feed = feedparser.parse(str(feed_path))
        assert len(feed.entries) == 53  # All 53 entries should be present
        
        # Verify newest entries are first
        first_entry_title = feed.entries[0].title
        assert "Test Comic - " in first_entry_title
        # Extract date from title and verify it's the newest
        date_str = first_entry_title.split(" - ")[1]
        assert date_str == new_entries[-1]['pub_date'].strftime("%Y-%m-%d")
    
    def test_regenerate_feed_at_limit(self, temp_feed_dir, comic_info, monkeypatch):
        """Test with exactly 100 entries after adding new ones."""
        monkeypatch.setattr('scripts.update_feeds.FEEDS_OUTPUT_DIR', Path(temp_feed_dir))
        
        # Create an existing feed with 97 entries
        generator = ComicFeedGenerator(output_dir=str(temp_feed_dir))
        existing_entries = create_test_entries(97)
        generator.generate_feed(comic_info, existing_entries)
        
        # Create 3 new entries
        newest_date = existing_entries[-1]['pub_date'] + timedelta(days=1)
        new_entries = create_test_entries(3, start_date=newest_date)
        
        result = regenerate_feed(comic_info, new_entries)
        
        assert result is True
        
        feed_path = Path(temp_feed_dir) / f"{comic_info['slug']}.xml"
        feed = feedparser.parse(str(feed_path))
        assert len(feed.entries) == 100  # Should be limited to 100
    
    def test_regenerate_feed_over_limit_bug_scenario(self, temp_feed_dir, comic_info, monkeypatch):
        """Test the exact bug scenario - 100+ existing entries with new entries.
        
        This test would have caught our bug! With 100+ existing entries,
        new entries should appear at the top, not be truncated.
        """
        monkeypatch.setattr('scripts.update_feeds.FEEDS_OUTPUT_DIR', Path(temp_feed_dir))
        
        # Create a feed with 100 existing entries
        generator = ComicFeedGenerator(output_dir=str(temp_feed_dir))
        old_entries = create_test_entries(100, start_date=datetime.now(pytz.UTC) - timedelta(days=120))
        generator.generate_feed(comic_info, old_entries)
        
        # Now add 3 new entries for recent dates
        newest_date = datetime.now(pytz.UTC) - timedelta(days=2)
        new_entries = create_test_entries(3, start_date=newest_date)
        
        # This is where the bug would occur
        result = regenerate_feed(comic_info, new_entries)
        
        assert result is True
        
        # Parse the feed and check
        feed_path = Path(temp_feed_dir) / f"{comic_info['slug']}.xml"
        feed = feedparser.parse(str(feed_path))
        
        # Should have exactly 100 entries
        assert len(feed.entries) == 100
        
        # CRITICAL TEST: The first 3 entries should be our new ones
        # This is what failed before the fix!
        first_three_titles = [feed.entries[i].title for i in range(3)]
        expected_dates = [e['pub_date'].strftime("%Y-%m-%d") for e in reversed(new_entries)]
        
        for title, expected_date in zip(first_three_titles, expected_dates):
            assert expected_date in title, f"Expected {expected_date} in {title}"
    
    def test_regenerate_feed_entry_deduplication(self, temp_feed_dir, comic_info, monkeypatch):
        """Test that duplicate entries (same ID) are handled correctly."""
        monkeypatch.setattr('scripts.update_feeds.FEEDS_OUTPUT_DIR', Path(temp_feed_dir))
        
        # Create some existing entries
        existing_entries = create_test_entries(10)
        generator = ComicFeedGenerator(output_dir=str(temp_feed_dir))
        generator.generate_feed(comic_info, existing_entries)
        
        # Create new entries, including one duplicate
        new_entries = [
            existing_entries[5],  # Duplicate entry
            {
                'title': 'New Comic Entry',
                'url': 'https://www.gocomics.com/test-comic/2024/07/19',
                'id': 'https://www.gocomics.com/test-comic/2024/07/19',
                'image_url': 'https://example.com/new.jpg',
                'description': 'New comic',
                'pub_date': datetime.now(pytz.UTC)
            }
        ]
        
        result = regenerate_feed(comic_info, new_entries)
        
        assert result is True
        
        feed_path = Path(temp_feed_dir) / f"{comic_info['slug']}.xml"
        feed = feedparser.parse(str(feed_path))
        
        # Should have 11 entries (10 original + 1 new, duplicate ignored)
        assert len(feed.entries) == 11
    
    def test_regenerate_feed_empty_initial(self, temp_feed_dir, comic_info, monkeypatch):
        """Test creating a feed from scratch."""
        monkeypatch.setattr('scripts.update_feeds.FEEDS_OUTPUT_DIR', Path(temp_feed_dir))
        
        new_entries = create_test_entries(5)
        result = regenerate_feed(comic_info, new_entries)
        
        assert result is True
        
        feed_path = Path(temp_feed_dir) / f"{comic_info['slug']}.xml"
        assert feed_path.exists()
        
        feed = feedparser.parse(str(feed_path))
        assert len(feed.entries) == 5
    
    def test_regenerate_feed_ordering(self, temp_feed_dir, comic_info, monkeypatch):
        """Test that entries are always ordered newest first in the final feed."""
        monkeypatch.setattr('scripts.update_feeds.FEEDS_OUTPUT_DIR', Path(temp_feed_dir))
        
        # Create entries with mixed dates
        entries = []
        base_date = datetime.now(pytz.UTC) - timedelta(days=10)
        
        # Add entries in random order
        for day_offset in [5, 1, 9, 3, 7, 2, 8, 4, 6, 0]:
            date = base_date + timedelta(days=day_offset)
            entries.append({
                'title': f'Comic - {date.strftime("%Y-%m-%d")}',
                'url': f'https://example.com/{day_offset}',
                'id': f'https://example.com/{day_offset}',
                'image_url': f'https://example.com/img-{day_offset}.jpg',
                'description': f'Comic for day {day_offset}',
                'pub_date': date
            })
        
        result = regenerate_feed(comic_info, entries)
        assert result is True
        
        feed_path = Path(temp_feed_dir) / f"{comic_info['slug']}.xml"
        feed = feedparser.parse(str(feed_path))
        
        # Extract dates from entries and verify they're in descending order
        dates = []
        for entry in feed.entries:
            # Parse date from title
            date_str = entry.title.split(" - ")[1]
            dates.append(date_str)
        
        # Verify dates are in descending order (newest first)
        for i in range(len(dates) - 1):
            assert dates[i] >= dates[i + 1], f"Dates not in order: {dates[i]} should be >= {dates[i + 1]}"


class TestHelperFunctions:
    """Test helper functions used in update_feeds.py."""
    
    def test_extract_image_from_description(self):
        """Test extracting image URLs from HTML descriptions."""
        # Test with valid image
        html = '<div><img src="https://example.com/comic.jpg" alt="Comic"><p>Description</p></div>'
        result = extract_image_from_description(html)
        assert result == "https://example.com/comic.jpg"
        
        # Test with no image
        html = '<div><p>No image here</p></div>'
        result = extract_image_from_description(html)
        assert result is None
        
        # Test with empty string
        result = extract_image_from_description("")
        assert result is None
        
        # Test with None
        result = extract_image_from_description(None)
        assert result is None