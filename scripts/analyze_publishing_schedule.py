#!/usr/bin/env python3
"""
Publishing Schedule Analyzer
Analyzes comic publishing frequencies to optimize update schedules.
"""

import logging
import re
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from comiccaster.http_client import ComicHTTPClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PublishingAnalyzer:
    """Analyzes comic publishing schedules to determine update frequency."""
    
    def __init__(self, base_url: str = "https://www.gocomics.com"):
        self.base_url = base_url
        self.client = ComicHTTPClient(base_url)
    
    def analyze_schedule(self, dates: List[datetime]) -> Dict[str, any]:
        """Analyze a list of publication dates to determine frequency."""
        if len(dates) < 3:
            return {
                'type': 'unknown',
                'confidence': 0,
                'reason': 'insufficient_data',
                'days_per_week': 0
            }
        
        # Sort dates
        dates = sorted(dates)
        
        # Calculate gaps between consecutive dates
        gaps = []
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i-1]).days
            gaps.append(gap)
        
        # Analyze gap patterns
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        min_gap = min(gaps) if gaps else 0
        max_gap = max(gaps) if gaps else 0
        
        # Count weekday occurrences
        weekday_counts = Counter(date.weekday() for date in dates)
        publishes_on_weekends = any(date.weekday() >= 5 for date in dates)
        
        # Determine publishing type
        result = {
            'average_gap_days': avg_gap,
            'min_gap_days': min_gap,
            'max_gap_days': max_gap,
            'publishes_on_weekends': publishes_on_weekends
        }
        
        # Daily publishing (7 days a week)
        if avg_gap <= 1.2 and max_gap <= 2:
            result.update({
                'type': 'daily',
                'days_per_week': 7,
                'confidence': 0.95 if avg_gap <= 1.1 else 0.90
            })
        
        # Weekday publishing (Mon-Fri)
        elif not publishes_on_weekends and avg_gap <= 1.5:
            result.update({
                'type': 'weekdays',
                'days_per_week': 5,
                'confidence': 0.95 if max_gap <= 3 else 0.90
            })
        
        # Weekly publishing
        elif 6 <= avg_gap <= 8 and min_gap >= 5:
            result.update({
                'type': 'weekly',
                'days_per_week': 1,
                'confidence': 0.95 if 6.5 <= avg_gap <= 7.5 else 0.90
            })
        
        # Semi-weekly (2-3 times per week)
        elif 2 <= avg_gap <= 4:
            days_per_week = round(7 / avg_gap)
            result.update({
                'type': 'semi-weekly',
                'days_per_week': days_per_week,
                'confidence': 0.85
            })
        
        # Irregular publishing
        else:
            result.update({
                'type': 'irregular',
                'days_per_week': round(7 / avg_gap) if avg_gap > 0 else 0,
                'confidence': 0.5
            })
        
        return result
    
    def fetch_comic_history(self, comic_slug: str, days: int = 30) -> List[datetime]:
        """Fetch historical comic dates from GoComics."""
        try:
            # GoComics doesn't have a simple archive page, so we'll check dates
            # by trying to fetch comics for the past N days
            dates = []
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            current_date = start_date
            while current_date <= end_date:
                url = f"{self.base_url}/{comic_slug}/{current_date.strftime('%Y/%m/%d')}"
                
                response = self.client.get(url, timeout=5)
                if response:
                    # Check if comic exists for this date
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Look for comic image or error message
                    if soup.find('img', class_=re.compile(r'comic.*image', re.I)) or \
                       soup.find('meta', property='og:image'):
                        dates.append(current_date)
                        logger.debug(f"Found comic for {comic_slug} on {current_date.strftime('%Y-%m-%d')}")
                
                current_date += timedelta(days=1)
            
            logger.info(f"Found {len(dates)} comics for {comic_slug} in last {days} days")
            return dates
            
        except Exception as e:
            logger.error(f"Error fetching comic history: {e}")
            return []
    
    def analyze_multiple_comics(self, comics: List[Dict[str, str]]) -> List[Dict[str, any]]:
        """Analyze publishing schedules for multiple comics."""
        results = []
        
        for comic in comics:
            logger.info(f"Analyzing {comic['name']}...")
            dates = self.fetch_comic_history(comic['slug'], days=30)
            
            if dates:
                frequency = self.analyze_schedule(dates)
                comic_with_freq = comic.copy()
                comic_with_freq['publishing_frequency'] = frequency
                results.append(comic_with_freq)
            else:
                comic_with_freq = comic.copy()
                comic_with_freq['publishing_frequency'] = {
                    'type': 'unknown',
                    'confidence': 0,
                    'reason': 'no_data_found'
                }
                results.append(comic_with_freq)
        
        return results
    
    def recommend_update_frequency(self, frequency: Dict[str, any]) -> str:
        """Recommend optimal update frequency based on publishing schedule."""
        freq_type = frequency.get('type', 'unknown')
        
        if freq_type == 'daily':
            return 'daily'
        elif freq_type == 'weekdays':
            return 'daily'  # Still check daily to catch Monday comics on weekends
        elif freq_type == 'weekly':
            return 'weekly'
        elif freq_type == 'semi-weekly':
            return 'smart'  # Smart detection based on actual publishing days
        elif freq_type == 'irregular':
            return 'smart'  # Smart detection with adaptive checking
        else:
            return 'daily'  # Default to daily for unknown patterns


def main():
    """Main function to analyze political comics publishing schedules."""
    analyzer = PublishingAnalyzer()
    
    # Example: Analyze a few known political comics
    test_comics = [
        {'slug': 'algoodwyn', 'name': 'Al Goodwyn'},
        {'slug': 'clayjones', 'name': 'Clay Jones'},
        {'slug': 'lisabenson', 'name': 'Lisa Benson'}
    ]
    
    results = analyzer.analyze_multiple_comics(test_comics)
    
    for comic in results:
        freq = comic['publishing_frequency']
        logger.info(f"{comic['name']}: {freq['type']} "
                   f"({freq.get('days_per_week', 0)} days/week, "
                   f"confidence: {freq.get('confidence', 0):.2f})")
    
    return 0


if __name__ == "__main__":
    exit(main())