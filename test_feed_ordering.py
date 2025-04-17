#!/usr/bin/env python3
"""
Test script to verify feed entry ordering.
This script tests that entries in the feed are properly sorted by date (newest first).
"""

import os
import sys
import time
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add the current directory to the path so we can import the comiccaster module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from comiccaster.feed_generator import ComicFeedGenerator

def test_feed_ordering():
    """Test that feed entries are properly ordered by date (newest first)."""
    print("Testing feed entry ordering...")
    
    # Create a test directory for feeds
    test_dir = Path("test_feeds")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Initialize the feed generator
        generator = ComicFeedGenerator(output_dir=str(test_dir))
        
        # Sample comic info
        comic_info = {
            "name": "Test Comic",
            "author": "Test Author",
            "url": "https://example.com/test-comic",
            "slug": "test-comic"
        }
        
        # Create entries with different dates (oldest to newest)
        entries = []
        base_date = datetime.now(timezone.utc)
        
        for i in range(5):
            date = base_date - timedelta(days=4-i)  # This will create dates from oldest to newest
            entries.append({
                "title": f"Test Comic - {date.strftime('%Y-%m-%d')}",
                "url": f"https://example.com/test-comic/{date.strftime('%Y/%m/%d')}",
                "image": f"https://example.com/test-comic/image_{i}.jpg",
                "description": f"Test description for {date.strftime('%Y-%m-%d')}",
                "pub_date": date.strftime('%a, %d %b %Y %H:%M:%S %z')
            })
        
        # Generate the feed
        print("Generating feed with test entries...")
        success = generator.generate_feed(comic_info, entries)
        
        if not success:
            print("Failed to generate feed!")
            return False
        
        # Parse the generated feed
        feed_path = test_dir / f"{comic_info['slug']}.xml"
        if not feed_path.exists():
            print(f"Feed file not found at {feed_path}")
            return False
        
        # Read and parse the feed
        from feedparser import parse
        feed = parse(str(feed_path))
        
        # Check entry ordering
        print("\nChecking entry ordering...")
        dates = []
        for entry in feed.entries:
            pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            dates.append(pub_date)
            print(f"Entry date: {pub_date}")
        
        # Verify dates are in reverse chronological order (newest first)
        is_ordered = all(dates[i] >= dates[i+1] for i in range(len(dates)-1))
        print(f"\nEntries are in correct order (newest first): {is_ordered}")
        
        return is_ordered
        
    finally:
        # Clean up - remove test directory and all its contents
        if test_dir.exists():
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    success = test_feed_ordering()
    sys.exit(0 if success else 1) 