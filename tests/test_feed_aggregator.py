"""Tests for the FeedAggregator class."""

import pytest
import os
from datetime import datetime
import pytz
from unittest.mock import patch, mock_open, MagicMock
from comiccaster.feed_aggregator import FeedAggregator

@pytest.fixture
def feed_aggregator():
    """Create a FeedAggregator instance for testing."""
    return FeedAggregator(feeds_dir='test_feeds')

@pytest.fixture
def mock_feed_content():
    """Mock RSS feed content."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Comic Feed</title>
            <link>http://example.com/comic</link>
            <description>Test comic feed</description>
            <item>
                <title>Test Comic Strip</title>
                <link>http://example.com/comic/1</link>
                <description>A funny test comic</description>
                <pubDate>Thu, 01 Jan 2024 12:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>'''

def test_feed_aggregator_initialization():
    """Test FeedAggregator initialization."""
    aggregator = FeedAggregator(feeds_dir='custom_feeds')
    assert aggregator.feeds_dir == 'custom_feeds'
    assert aggregator.feed_generator is not None
    
    # Test default feed properties
    feed_str = aggregator.feed_generator.rss_str(pretty=True).decode('utf-8')
    assert 'ComicCaster Combined Feed' in feed_str
    assert 'A combined feed of your favorite comics' in feed_str
    assert 'https://comiccaster.xyz' in feed_str
    assert '<language>en</language>' in feed_str

@patch('os.path.exists')
@patch('feedparser.parse')
def test_load_feed_entries(mock_parse, mock_exists, feed_aggregator, mock_feed_content):
    """Test loading entries from a feed file."""
    mock_exists.return_value = True
    
    # Mock the feedparser response
    mock_entry = MagicMock()
    mock_entry.title = 'Test Comic Strip'
    mock_entry.link = 'http://example.com/comic/1'
    mock_entry.description = 'A funny test comic'
    mock_entry.published_parsed.timestamp.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=pytz.UTC).timestamp()
    
    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]
    mock_parse.return_value = mock_feed
    
    entries = feed_aggregator.load_feed_entries('test-comic')
    assert len(entries) == 1
    entry = entries[0]
    assert entry['title'] == 'Test Comic Strip'
    assert entry['link'] == 'http://example.com/comic/1'
    assert entry['description'] == 'A funny test comic'
    assert isinstance(entry['published'], datetime)
    assert entry['comic'] == 'test-comic'

def test_load_feed_entries_nonexistent_file(feed_aggregator):
    """Test loading entries from a non-existent feed file."""
    entries = feed_aggregator.load_feed_entries('nonexistent-comic')
    assert entries == []

def test_add_entry(feed_aggregator):
    """Test adding an entry to the feed."""
    entry_data = {
        'title': 'Test Entry',
        'link': 'http://example.com/test',
        'description': 'Test description',
        'published': datetime.now(pytz.UTC)
    }
    
    feed_aggregator.add_entry(entry_data)
    feed_str = feed_aggregator.feed_generator.rss_str(pretty=True).decode('utf-8')
    
    assert 'Test Entry' in feed_str
    assert 'http://example.com/test' in feed_str
    assert 'Test description' in feed_str

def test_add_entry_with_string_date(feed_aggregator):
    """Test adding an entry with a string date."""
    entry_data = {
        'title': 'Test Entry',
        'link': 'http://example.com/test',
        'description': 'Test description',
        'published': '2024-01-01T12:00:00Z'
    }
    
    feed_aggregator.add_entry(entry_data)
    feed_str = feed_aggregator.feed_generator.rss_str(pretty=True).decode('utf-8')
    
    assert 'Test Entry' in feed_str
    assert 'Mon, 01 Jan 2024 12:00:00 +0000' in feed_str  # RFC 822 date format

def test_add_entry_missing_fields(feed_aggregator):
    """Test adding an entry with missing fields."""
    entry_data = {}  # Empty entry data
    
    feed_aggregator.add_entry(entry_data)
    feed_str = feed_aggregator.feed_generator.rss_str(pretty=True).decode('utf-8')
    
    assert 'Untitled' in feed_str  # Default title
    assert '<link>' in feed_str  # Empty link
    assert '<description>' in feed_str  # Empty description

def test_generate_feed(feed_aggregator):
    """Test generating a combined feed."""
    with patch.object(feed_aggregator, 'load_feed_entries') as mock_load:
        mock_load.return_value = [{
            'title': f'Comic {i}',
            'link': f'http://example.com/comic/{i}',
            'description': f'Description {i}',
            'published': datetime(2024, 1, i, tzinfo=pytz.UTC)
        } for i in range(1, 4)]
        
        feed_xml = feed_aggregator.generate_feed(['comic1', 'comic2'])
        
        # Verify the feed was generated
        assert isinstance(feed_xml, str)
        assert 'Comic 1' in feed_xml
        assert 'Comic 2' in feed_xml
        assert 'Comic 3' in feed_xml
        
        # Verify entries are sorted by date (most recent first)
        first_pos = feed_xml.find('Comic 3')
        second_pos = feed_xml.find('Comic 2')
        third_pos = feed_xml.find('Comic 1')
        assert first_pos < second_pos < third_pos

@patch('os.makedirs')
def test_save_feed(mock_makedirs, feed_aggregator, tmp_path):
    """Test saving a feed to a file."""
    output_file = tmp_path / 'test_feed.xml'
    feed_content = '<rss>Test feed content</rss>'
    
    feed_aggregator.save_feed(feed_content, str(output_file))
    
    # Verify the directory was created
    mock_makedirs.assert_called_once_with(str(tmp_path), exist_ok=True)
    
    # Verify the content was written
    with open(output_file) as f:
        assert f.read() == feed_content

def test_generate_feed_error_handling(feed_aggregator):
    """Test error handling in generate_feed."""
    with patch.object(feed_aggregator, 'load_feed_entries') as mock_load:
        mock_load.side_effect = Exception('Test error')
        
        with pytest.raises(Exception) as exc_info:
            feed_aggregator.generate_feed(['comic1'])
        
        assert str(exc_info.value) == 'Test error'

def test_save_feed_error_handling(feed_aggregator):
    """Test error handling in save_feed."""
    with patch('os.makedirs') as mock_makedirs:
        mock_makedirs.side_effect = OSError('Test error')
        
        with pytest.raises(OSError) as exc_info:
            feed_aggregator.save_feed('test content', 'test.xml')
        
        assert 'Test error' in str(exc_info.value) 