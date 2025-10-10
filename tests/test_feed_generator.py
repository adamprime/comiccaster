"""Tests for the ComicFeedGenerator class."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
from feedgen.feed import FeedGenerator
from feedgen.entry import FeedEntry
from comiccaster.feed_generator import ComicFeedGenerator

@pytest.fixture
def comic_info():
    """Sample comic information."""
    return {
        'name': 'Test Comic',
        'author': 'Test Author',
        'url': 'https://www.gocomics.com/test-comic',
        'slug': 'test-comic'
    }

@pytest.fixture
def metadata():
    """Sample comic strip metadata."""
    return {
        'title': 'Test Comic - 2024-04-06',
        'url': 'https://www.gocomics.com/test-comic/2024/04/06',
        'image': 'https://example.com/test-comic.jpg',
        'description': 'Test comic strip for April 6, 2024',
        'pub_date': 'Sat, 06 Apr 2024 00:00:00 -0400'
    }

@pytest.fixture
def feed_generator(tmp_path):
    """Create a ComicFeedGenerator instance with a temporary output directory."""
    return ComicFeedGenerator(output_dir=str(tmp_path))

def test_initialization(tmp_path):
    """Test ComicFeedGenerator initialization."""
    generator = ComicFeedGenerator(
        base_url='https://example.com',
        output_dir=str(tmp_path)
    )
    
    assert generator.base_url == 'https://example.com'
    assert generator.output_dir == Path(tmp_path)
    assert generator.output_dir.exists()

def test_create_feed(feed_generator, comic_info):
    """Test creating a new feed."""
    fg = feed_generator.create_feed(comic_info)
    
    feed_str = fg.rss_str(pretty=True).decode('utf-8')
    assert 'Test Comic - GoComics' in feed_str
    assert comic_info['url'] in feed_str
    assert 'Daily Test Comic comic strip by Test Author' in feed_str
    assert '<language>en</language>' in feed_str
    assert comic_info['author'] in feed_str

def test_create_entry(feed_generator, comic_info, metadata):
    """Test creating a feed entry."""
    fe = feed_generator.create_entry(comic_info, metadata)

    # Create a properly configured feed generator for testing
    fg = feed_generator.create_feed(comic_info)
    fg.add_entry(fe)
    feed_str = fg.rss_str(pretty=True).decode('utf-8')

    # Title should now include day of week
    assert 'Sat 2024-04-06' in feed_str
    assert comic_info['name'] in feed_str
    assert metadata['url'] in feed_str
    assert metadata['image'] in feed_str
    assert metadata['description'] in feed_str

def test_create_entry_minimal_metadata(feed_generator, comic_info):
    """Test creating a feed entry with minimal metadata."""
    minimal_metadata = {'url': comic_info['url']}
    fe = feed_generator.create_entry(comic_info, minimal_metadata)
    
    # Create a properly configured feed generator for testing
    fg = feed_generator.create_feed(comic_info)
    fg.add_entry(fe)
    feed_str = fg.rss_str(pretty=True).decode('utf-8')
    
    assert comic_info['name'] in feed_str
    assert comic_info['url'] in feed_str
    # Check for date in ISO format (YYYY-MM-DD)
    current_date = datetime.now(timezone.utc)
    date_str = current_date.strftime('%Y-%m-%d')
    assert date_str in feed_str

def test_create_entry_invalid_date(feed_generator, comic_info, metadata):
    """Test creating a feed entry with invalid publication date."""
    metadata['pub_date'] = 'invalid date'
    fe = feed_generator.create_entry(comic_info, metadata)

    # Create a properly configured feed generator for testing
    fg = feed_generator.create_feed(comic_info)
    fg.add_entry(fe)
    feed_str = fg.rss_str(pretty=True).decode('utf-8')

    # Should still create entry with current date (with day of week)
    assert comic_info['name'] in feed_str
    assert metadata['url'] in feed_str
    # Should have a day abbreviation in the title
    import re
    assert re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)', feed_str) is not None

def test_update_feed_new(feed_generator, comic_info, metadata):
    """Test updating a non-existent feed (creates new)."""
    result = feed_generator.update_feed(comic_info, metadata)

    assert result is True
    feed_path = feed_generator.output_dir / f"{comic_info['slug']}.xml"
    assert feed_path.exists()

    with open(feed_path) as f:
        feed_content = f.read()
        # Title should include day of week
        assert 'Sat 2024-04-06' in feed_content
        assert comic_info['name'] in feed_content
        assert metadata['url'] in feed_content
        assert metadata['image'] in feed_content

@patch('pathlib.Path.exists')
def test_update_feed_existing(mock_exists, feed_generator, comic_info, metadata):
    """Test updating an existing feed."""
    mock_exists.return_value = True

    # Create a new feed first
    fg = feed_generator.create_feed(comic_info)
    feed_path = feed_generator.output_dir / f"{comic_info['slug']}.xml"
    fg.rss_file(str(feed_path))

    # Now update it
    result = feed_generator.update_feed(comic_info, metadata)
    assert result is True

    # Verify the feed was updated with day of week in title
    with open(feed_path) as f:
        feed_content = f.read()
        assert 'Sat 2024-04-06' in feed_content
        assert comic_info['name'] in feed_content
        assert metadata['url'] in feed_content
        assert metadata['image'] in feed_content

def test_update_feed_error(feed_generator, comic_info, metadata):
    """Test error handling in update_feed."""
    with patch('feedgen.feed.FeedGenerator.rss_file') as mock_rss_file:
        mock_rss_file.side_effect = Exception('Test error')
        result = feed_generator.update_feed(comic_info, metadata)
        
        assert result is False

def test_generate_feed(feed_generator, comic_info):
    """Test generating a complete feed with multiple entries."""
    entries = [
        {
            'title': f'Test Comic - Day {i}',
            'url': f'https://example.com/comic/{i}',
            'image': f'https://example.com/image/{i}.jpg',
            'description': f'Test description {i}',
            'pub_date': f'Sun, {i} Apr 2024 00:00:00 -0400'
        }
        for i in range(1, 4)
    ]

    result = feed_generator.generate_feed(comic_info, entries)

    assert result is True
    feed_path = feed_generator.output_dir / f"{comic_info['slug']}.xml"
    assert feed_path.exists()

    with open(feed_path) as f:
        feed_content = f.read()
        # Verify entries are present with day-of-week format
        # Apr 1, 2024 = Mon, Apr 2 = Tue, Apr 3 = Wed
        day_abbrevs = ['Mon', 'Tue', 'Wed']
        for i, day in enumerate(range(1, 4), 0):
            assert f'{day_abbrevs[i]} 2024-04-0{day}' in feed_content
            assert f'https://example.com/comic/{day}' in feed_content
            assert f'Test description {day}' in feed_content

def test_generate_feed_error(feed_generator, comic_info):
    """Test error handling in generate_feed."""
    with patch('feedgen.feed.FeedGenerator.rss_file') as mock_rss_file:
        mock_rss_file.side_effect = Exception('Test error')
        result = feed_generator.generate_feed(comic_info, [])

        assert result is False

def test_entry_title_includes_day_of_week(feed_generator, comic_info):
    """Test that feed entry titles include the day of week abbreviation."""
    # Test with a known date: Saturday, April 6, 2024
    metadata = {
        'title': 'Test Comic - 2024-04-06',
        'url': 'https://www.gocomics.com/test-comic/2024/04/06',
        'image': 'https://example.com/test-comic.jpg',
        'description': 'Test comic strip',
        'pub_date': 'Sat, 06 Apr 2024 00:00:00 -0400'
    }

    fe = feed_generator.create_entry(comic_info, metadata)

    # Create a properly configured feed generator for testing
    fg = feed_generator.create_feed(comic_info)
    fg.add_entry(fe)
    feed_str = fg.rss_str(pretty=True).decode('utf-8')

    # Should include "Sat" for Saturday
    assert 'Sat 2024-04-06' in feed_str
    assert comic_info['name'] in feed_str

def test_entry_title_day_of_week_for_different_days(feed_generator, comic_info):
    """Test that day-of-week abbreviations are correct for different days."""
    test_cases = [
        {'pub_date': 'Mon, 01 Apr 2024 00:00:00 -0400', 'expected_day': 'Mon', 'expected_date': '2024-04-01'},
        {'pub_date': 'Tue, 02 Apr 2024 00:00:00 -0400', 'expected_day': 'Tue', 'expected_date': '2024-04-02'},
        {'pub_date': 'Wed, 03 Apr 2024 00:00:00 -0400', 'expected_day': 'Wed', 'expected_date': '2024-04-03'},
        {'pub_date': 'Thu, 04 Apr 2024 00:00:00 -0400', 'expected_day': 'Thu', 'expected_date': '2024-04-04'},
        {'pub_date': 'Fri, 05 Apr 2024 00:00:00 -0400', 'expected_day': 'Fri', 'expected_date': '2024-04-05'},
        {'pub_date': 'Sat, 06 Apr 2024 00:00:00 -0400', 'expected_day': 'Sat', 'expected_date': '2024-04-06'},
        {'pub_date': 'Sun, 07 Apr 2024 00:00:00 -0400', 'expected_day': 'Sun', 'expected_date': '2024-04-07'},
    ]

    for test_case in test_cases:
        metadata = {
            'url': 'https://www.gocomics.com/test-comic',
            'image': 'https://example.com/test.jpg',
            'pub_date': test_case['pub_date']
        }

        fe = feed_generator.create_entry(comic_info, metadata)
        fg = feed_generator.create_feed(comic_info)
        fg.add_entry(fe)
        feed_str = fg.rss_str(pretty=True).decode('utf-8')

        expected_title_part = f"{test_case['expected_day']} {test_case['expected_date']}"
        assert expected_title_part in feed_str, f"Expected '{expected_title_part}' in feed for {test_case['pub_date']}" 