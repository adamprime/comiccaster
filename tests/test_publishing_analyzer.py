"""
Test suite for analyzing political comic publishing schedules.
Following TDD principles - these tests are written before implementation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch


class TestPublishingAnalyzer:
    """Test cases for analyzing comic publishing frequencies."""
    
    @pytest.fixture
    def daily_comic_dates(self):
        """Generate dates for a daily publishing comic."""
        base_date = datetime(2025, 7, 1)
        return [base_date + timedelta(days=i) for i in range(30)]
    
    @pytest.fixture
    def weekday_comic_dates(self):
        """Generate dates for a weekday-only comic (Mon-Fri)."""
        base_date = datetime(2025, 7, 1)
        dates = []
        for i in range(30):
            date = base_date + timedelta(days=i)
            if date.weekday() < 5:  # Monday = 0, Friday = 4
                dates.append(date)
        return dates
    
    @pytest.fixture
    def weekly_comic_dates(self):
        """Generate dates for a weekly comic."""
        base_date = datetime(2025, 7, 1)
        return [base_date + timedelta(weeks=i) for i in range(4)]
    
    @pytest.fixture
    def irregular_comic_dates(self):
        """Generate irregular publishing dates."""
        base_date = datetime(2025, 7, 1)
        # Irregular pattern: some daily, then gap, then weekly
        dates = [
            base_date,
            base_date + timedelta(days=1),
            base_date + timedelta(days=2),
            base_date + timedelta(days=8),  # 6 day gap
            base_date + timedelta(days=15),  # 7 day gap
            base_date + timedelta(days=17),  # 2 day gap
            base_date + timedelta(days=25),  # 8 day gap
        ]
        return dates
    
    def test_analyze_daily_publisher(self, daily_comic_dates):
        """Test detecting daily publishing schedule."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        analyzer = PublishingAnalyzer()
        frequency = analyzer.analyze_schedule(daily_comic_dates)
        
        assert frequency['type'] == 'daily'
        assert frequency['days_per_week'] == 7
        assert frequency['confidence'] >= 0.95  # High confidence
        assert frequency['average_gap_days'] == 1.0
    
    def test_analyze_weekday_publisher(self, weekday_comic_dates):
        """Test detecting weekday-only publishing schedule."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        analyzer = PublishingAnalyzer()
        frequency = analyzer.analyze_schedule(weekday_comic_dates)
        
        assert frequency['type'] == 'weekdays'
        assert frequency['days_per_week'] == 5
        assert frequency['confidence'] >= 0.90
        assert frequency['publishes_on_weekends'] == False
    
    def test_analyze_weekly_publisher(self, weekly_comic_dates):
        """Test detecting weekly publishing schedule."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        analyzer = PublishingAnalyzer()
        frequency = analyzer.analyze_schedule(weekly_comic_dates)
        
        assert frequency['type'] == 'weekly'
        assert frequency['days_per_week'] == 1
        assert frequency['confidence'] >= 0.90
        assert frequency['average_gap_days'] == 7.0
    
    def test_analyze_semi_weekly_publisher(self):
        """Test detecting semi-weekly publishing (2-3 times per week)."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        # Create dates for Tuesday/Thursday publisher
        base_date = datetime(2025, 7, 1)
        dates = []
        for week in range(4):
            week_start = base_date + timedelta(weeks=week)
            dates.append(week_start + timedelta(days=1))  # Tuesday
            dates.append(week_start + timedelta(days=3))  # Thursday
        
        analyzer = PublishingAnalyzer()
        frequency = analyzer.analyze_schedule(dates)
        
        assert frequency['type'] == 'semi-weekly'
        assert frequency['days_per_week'] == 2
        assert frequency['confidence'] >= 0.85
    
    def test_analyze_irregular_publisher(self, irregular_comic_dates):
        """Test handling irregular schedules."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        analyzer = PublishingAnalyzer()
        frequency = analyzer.analyze_schedule(irregular_comic_dates)
        
        assert frequency['type'] == 'irregular'
        assert frequency['confidence'] < 0.7  # Low confidence
        assert 'average_gap_days' in frequency
        assert 'min_gap_days' in frequency
        assert 'max_gap_days' in frequency
    
    def test_insufficient_data(self):
        """Test handling insufficient data for analysis."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        analyzer = PublishingAnalyzer()
        
        # Only 2 dates - not enough for analysis
        dates = [datetime(2025, 7, 1), datetime(2025, 7, 2)]
        frequency = analyzer.analyze_schedule(dates)
        
        assert frequency['type'] == 'unknown'
        assert frequency['confidence'] == 0
        assert frequency['reason'] == 'insufficient_data'
    
    def test_fetch_comic_history(self):
        """Test fetching historical comic dates from GoComics."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        with patch('comiccaster.http_client.requests.Session.get') as mock_get:
            # Mock only specific dates to have comics
            def mock_response_func(url, *args, **kwargs):
                mock_resp = Mock()
                # Only these dates have comics
                if any(date in url for date in ['2025/07/17', '2025/07/15', '2025/07/14']):
                    mock_resp.status_code = 200
                    mock_resp.text = '<img class="comic-image" src="test.jpg">'
                else:
                    mock_resp.status_code = 404
                    mock_resp.text = 'No comic found'
                return mock_resp
            
            mock_get.side_effect = mock_response_func
            
            analyzer = PublishingAnalyzer()
            # Use a shorter date range for testing
            dates = analyzer.fetch_comic_history('algoodwyn', days=5)
            
            # Should find comics on the mocked dates within the range
            assert len(dates) >= 1  # At least one date should be found
            # The actual dates depend on current date, so we just verify format
            for date in dates:
                assert isinstance(date, datetime)
    
    def test_analyze_multiple_comics(self):
        """Test batch analysis of multiple comics."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        comics = [
            {'slug': 'algoodwyn', 'name': 'Al Goodwyn'},
            {'slug': 'clayjones', 'name': 'Clay Jones'},
            {'slug': 'lisabenson', 'name': 'Lisa Benson'}
        ]
        
        with patch.object(PublishingAnalyzer, 'fetch_comic_history') as mock_fetch:
            # Mock different schedules
            mock_fetch.side_effect = [
                [datetime(2025, 7, i) for i in range(1, 8)],  # Daily
                [datetime(2025, 7, i*7) for i in range(1, 5)],  # Weekly
                [datetime(2025, 7, i*3) for i in range(1, 10)]  # Semi-weekly
            ]
            
            analyzer = PublishingAnalyzer()
            results = analyzer.analyze_multiple_comics(comics)
            
            assert len(results) == 3
            assert results[0]['publishing_frequency']['type'] == 'daily'
            assert results[1]['publishing_frequency']['type'] == 'weekly'
            assert results[2]['publishing_frequency']['type'] == 'semi-weekly'
    
    def test_recommend_update_frequency(self):
        """Test recommending optimal update frequency based on publishing schedule."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        analyzer = PublishingAnalyzer()
        
        # Daily comic should update daily
        daily_freq = {'type': 'daily', 'days_per_week': 7}
        assert analyzer.recommend_update_frequency(daily_freq) == 'daily'
        
        # Weekly comic should update weekly
        weekly_freq = {'type': 'weekly', 'days_per_week': 1}
        assert analyzer.recommend_update_frequency(weekly_freq) == 'weekly'
        
        # Irregular comic should update with smart detection
        irregular_freq = {'type': 'irregular', 'average_gap_days': 4.5}
        assert analyzer.recommend_update_frequency(irregular_freq) == 'smart'
    
    @pytest.mark.network
    def test_integration_analyze_real_comic(self):
        """Integration test - analyze real comic from GoComics."""
        from scripts.analyze_publishing_schedule import PublishingAnalyzer
        
        analyzer = PublishingAnalyzer()
        
        # Test with a known political cartoonist
        dates = analyzer.fetch_comic_history('algoodwyn', days=30)
        frequency = analyzer.analyze_schedule(dates)
        
        assert frequency['type'] in ['daily', 'weekdays', 'weekly', 'semi-weekly', 'irregular']
        assert frequency['confidence'] > 0
        assert 'days_per_week' in frequency