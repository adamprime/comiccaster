#!/usr/bin/env python3
"""
Test script for the ComicFeedGenerator class.
This script tests the feed generator functionality with sample data.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the current directory to the path so we can import the comiccaster module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from comiccaster.feed_generator import ComicFeedGenerator

def test_feed_generator():
    """Test the ComicFeedGenerator class with sample data."""
    print("Testing ComicFeedGenerator...")
    
    # Create a test directory for feeds
    test_dir = Path("test_feeds")
    test_dir.mkdir(exist_ok=True)
    
    # Initialize the feed generator
    generator = ComicFeedGenerator(output_dir=str(test_dir))
    
    # Sample comic info
    comic_info = {
        "name": "Test Comic",
        "author": "Test Author",
        "url": "https://example.com/test-comic",
        "slug": "test-comic"
    }
    
    # Sample metadata for a new entry
    metadata = {
        "title": "Test Comic - 2023-01-01",
        "url": "https://example.com/test-comic/2023/01/01",
        "image": "https://example.com/test-comic/image.jpg",
        "description": "This is a test comic entry.",
        "pub_date": "Sun, 01 Jan 2023 12:00:00 +0000"
    }
    
    # Test creating a new feed
    print("Testing create_feed...")
    feed = generator.create_feed(comic_info)
    print(f"Feed created: {feed.title()}")
    
    # Test creating a feed entry
    print("Testing create_entry...")
    entry = generator.create_entry(comic_info, metadata)
    print(f"Entry created: {entry.title()}")
    
    # Test updating a feed
    print("Testing update_feed...")
    result = generator.update_feed(comic_info, metadata)
    print(f"Feed update result: {'Success' if result else 'Failed'}")
    
    # Check if the feed file was created
    feed_path = test_dir / f"{comic_info['slug']}.xml"
    if feed_path.exists():
        print(f"Feed file created at: {feed_path}")
        print(f"Feed file size: {feed_path.stat().st_size} bytes")
    else:
        print("Feed file was not created!")
    
    # Test with a second entry
    print("\nTesting with a second entry...")
    metadata2 = {
        "title": "Test Comic - 2023-01-02",
        "url": "https://example.com/test-comic/2023/01/02",
        "image": "https://example.com/test-comic/image2.jpg",
        "description": "This is another test comic entry.",
        "pub_date": "Mon, 02 Jan 2023 12:00:00 +0000"
    }
    
    result = generator.update_feed(comic_info, metadata2)
    print(f"Second feed update result: {'Success' if result else 'Failed'}")
    
    # Check the updated feed file
    if feed_path.exists():
        print(f"Updated feed file size: {feed_path.stat().st_size} bytes")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_feed_generator() 