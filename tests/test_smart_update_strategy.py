"""
Test suite for smart update strategy in feed generation.
Following TDD principles - these tests are written before implementation.
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


class TestSmartUpdateStrategy:
    """Test cases for implementing smart update frequencies based on comic publishing patterns."""
    
    @pytest.fixture
    def daily_comic(self):
        """Comic that publishes daily."""
        return {
            'name': 'Clay Jones',
            'slug': 'clayjones',
            'publishing_frequency': {
                'type': 'daily',
                'days_per_week': 7,
                'confidence': 0.95
            },
            'update_recommendation': 'daily'
        }
    
    @pytest.fixture
    def weekly_comic(self):
        """Comic that publishes weekly."""
        return {
            'name': 'Brian McFadden',
            'slug': 'brian-mcfadden',
            'publishing_frequency': {
                'type': 'weekly',
                'days_per_week': 1,
                'confidence': 0.95,
                'average_gap_days': 7.0
            },
            'update_recommendation': 'weekly'
        }
    
    @pytest.fixture
    def irregular_comic(self):
        """Comic with irregular publishing schedule."""
        return {
            'name': 'Al Goodwyn',
            'slug': 'algoodwyn',
            'publishing_frequency': {
                'type': 'irregular',
                'days_per_week': 4,
                'confidence': 0.5,
                'average_gap_days': 1.67
            },
            'update_recommendation': 'smart'
        }
    
    @pytest.fixture
    def political_comics_list(self, daily_comic, weekly_comic, irregular_comic):
        """Sample political comics list with different update patterns."""
        return [daily_comic, weekly_comic, irregular_comic]
    
    def test_load_political_comics_list(self):
        """Test loading political comics list alongside regular comics."""
        from scripts.update_feeds import load_political_comics_list
        
        mock_data = [{'name': 'Test Comic', 'slug': 'test'}]
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            comics = load_political_comics_list()
            assert comics == mock_data
    
    def test_should_update_daily_comic(self, daily_comic):
        """Test that daily comics are always updated."""
        from scripts.update_feeds import should_update_comic
        
        # Daily comics should always update
        assert should_update_comic(daily_comic, datetime.now()) == True
        
        # Even if last updated today
        last_update = datetime.now()
        assert should_update_comic(daily_comic, last_update) == True
    
    def test_should_update_weekly_comic(self, weekly_comic):
        """Test that weekly comics update once per week."""
        from scripts.update_feeds import should_update_comic
        
        # Should update if never updated
        assert should_update_comic(weekly_comic, None) == True
        
        # Should not update if updated 3 days ago
        last_update = datetime.now() - timedelta(days=3)
        assert should_update_comic(weekly_comic, last_update) == False
        
        # Should update if updated 8 days ago
        last_update = datetime.now() - timedelta(days=8)
        assert should_update_comic(weekly_comic, last_update) == True
    
    def test_should_update_irregular_comic(self, irregular_comic):
        """Test smart update logic for irregular comics."""
        from scripts.update_feeds import should_update_comic
        
        # Should always check if never updated
        assert should_update_comic(irregular_comic, None) == True
        
        # Should check based on average gap
        # Average gap is 1.67 days, so check after 2 days
        last_update = datetime.now() - timedelta(days=1)
        assert should_update_comic(irregular_comic, last_update) == False
        
        last_update = datetime.now() - timedelta(days=3)
        assert should_update_comic(irregular_comic, last_update) == True
    
    def test_get_update_frequency_days(self):
        """Test calculation of update frequency in days."""
        from scripts.update_feeds import get_update_frequency_days
        
        # Daily comic
        assert get_update_frequency_days({'update_recommendation': 'daily'}) == 1
        
        # Weekly comic
        assert get_update_frequency_days({'update_recommendation': 'weekly'}) == 7
        
        # Smart update with average gap
        comic = {
            'update_recommendation': 'smart',
            'publishing_frequency': {'average_gap_days': 2.5}
        }
        assert get_update_frequency_days(comic) == 3  # Rounds up
        
        # Unknown pattern defaults to daily
        assert get_update_frequency_days({'update_recommendation': 'unknown'}) == 1
    
    def test_load_last_update_times(self):
        """Test loading last update times from tracking file."""
        from scripts.update_feeds import load_last_update_times
        
        mock_data = {
            'clayjones': '2025-07-17T10:00:00',
            'algoodwyn': '2025-07-16T10:00:00'
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            times = load_last_update_times()
            assert 'clayjones' in times
            assert isinstance(times['clayjones'], datetime)
    
    def test_save_last_update_times(self):
        """Test saving last update times to tracking file."""
        from scripts.update_feeds import save_last_update_times
        
        update_times = {
            'clayjones': datetime.now(),
            'algoodwyn': datetime.now() - timedelta(days=1)
        }
        
        mock_file = mock_open()
        with patch('builtins.open', mock_file):
            save_last_update_times(update_times)
            
        # Verify write was called
        mock_file().write.assert_called()
    
    def test_filter_comics_for_update(self, political_comics_list):
        """Test filtering comics based on update schedule."""
        from scripts.update_feeds import filter_comics_for_update
        
        # Mock last update times
        last_updates = {
            'clayjones': datetime.now() - timedelta(hours=1),  # Updated 1 hour ago
            'brian-mcfadden': datetime.now() - timedelta(days=3),  # Updated 3 days ago
            # algoodwyn has no last update
        }
        
        comics_to_update = filter_comics_for_update(political_comics_list, last_updates)
        
        # Daily comic should update (always)
        assert any(c['slug'] == 'clayjones' for c in comics_to_update)
        
        # Weekly comic should not update (only 3 days ago)
        assert not any(c['slug'] == 'brian-mcfadden' for c in comics_to_update)
        
        # Irregular comic with no last update should update
        assert any(c['slug'] == 'algoodwyn' for c in comics_to_update)
    
    def test_update_feeds_with_smart_scheduling(self):
        """Test the main update process with smart scheduling."""
        from scripts.update_feeds import update_feeds_smart
        
        mock_comics = [
            {'name': 'Daily Comic', 'slug': 'daily', 'update_recommendation': 'daily'},
            {'name': 'Weekly Comic', 'slug': 'weekly', 'update_recommendation': 'weekly'}
        ]
        
        with patch('scripts.update_feeds.load_comics_list') as mock_load_comics, \
             patch('scripts.update_feeds.load_political_comics_list') as mock_load_political, \
             patch('scripts.update_feeds.load_last_update_times') as mock_load_times, \
             patch('scripts.update_feeds.filter_comics_for_update') as mock_filter, \
             patch('scripts.update_feeds.update_comic_feed') as mock_update:
            
            mock_load_comics.return_value = []
            mock_load_political.return_value = mock_comics
            mock_load_times.return_value = {}
            mock_filter.return_value = [mock_comics[0]]  # Only daily comic needs update
            
            update_feeds_smart()
            
            # Verify only filtered comics were updated
            assert mock_update.call_count == 1
            mock_update.assert_called_with(mock_comics[0])
    
    def test_backoff_strategy_for_failures(self):
        """Test exponential backoff for comics that consistently fail."""
        from scripts.update_feeds import calculate_backoff_days
        
        # No failures - normal schedule
        assert calculate_backoff_days(0, base_days=1) == 1
        
        # 1 failure - double the interval
        assert calculate_backoff_days(1, base_days=1) == 2
        
        # 3 failures - 8x the interval
        assert calculate_backoff_days(3, base_days=1) == 8
        
        # Max backoff of 30 days
        assert calculate_backoff_days(10, base_days=7) == 30