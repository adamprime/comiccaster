#!/usr/bin/env python3
"""
Test script for the ComicFeedGenerator to check image duplication issues.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from comiccaster.feed_generator import ComicFeedGenerator

def test_no_image_duplication():
    """Test that images are not duplicated in feed entries."""
    print("Testing image duplication prevention in ComicFeedGenerator...")
    
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
        "slug": "test-comic-nodupe"
    }
    
    # Sample image URLs
    image_url = "https://example.com/test-comic/image.jpg"
    existing_image_url = "https://example.com/test-comic/existing-image.jpg"
    
    # Test case 1: Normal case - image URL in image_url field only
    print("\nTest 1: Normal case - image in image_url field only")
    metadata1 = {
        "title": "Test Comic - Case 1",
        "url": "https://example.com/test-comic/case1",
        "image_url": image_url,
        "description": "This is a test entry without image in description.",
        "pub_date": "Mon, 01 Jan 2023 12:00:00 +0000"
    }
    
    # Test case 2: Different image already in description text
    print("\nTest 2: Different image already in description")
    metadata2 = {
        "title": "Test Comic - Case 2",
        "url": "https://example.com/test-comic/case2",
        "image_url": image_url,
        "description": f'<img src="{existing_image_url}" alt="Test Comic" />This already has an image.',
        "pub_date": "Tue, 02 Jan 2023 12:00:00 +0000"
    }
    
    # Generate feed
    entries = [metadata1, metadata2]
    result = generator.generate_feed(comic_info, entries)
    print(f"Feed generation result: {'Success' if result else 'Failed'}")
    
    # Check the feed file
    feed_path = test_dir / f"{comic_info['slug']}.xml"
    if feed_path.exists():
        print(f"Feed file created at: {feed_path}")
        
        # Read the feed file and check for duplicated images
        with open(feed_path, 'r') as f:
            content = f.read()
            
            # Count occurrences of the image URL
            occurrences = content.count(image_url)
            print(f"Image URL appears {occurrences} times in the feed")
            
            # Analyze where the images appear
            enclosure_count = content.count(f'<enclosure url="{image_url}"')
            print(f"Found {enclosure_count} enclosure tags with image URL")
            
            img_tag_count = content.count(f'<img src="{image_url}"')
            print(f"Found {img_tag_count} img tags with image URL")
            
            # Check entries separately
            import xml.etree.ElementTree as ET
            tree = ET.parse(feed_path)
            root = tree.getroot()
            channel = root.find('channel')
            
            print("\nAnalyzing individual entries:")
            has_duplicates = False
            for i, item in enumerate(channel.findall('item')):
                title = item.find('title').text
                desc = item.find('description').text
                has_enclosure = any(enc.get('url') == image_url for enc in item.findall('enclosure'))
                
                print(f"\nEntry {i+1}: {title}")
                print(f"  Has enclosure with image URL: {has_enclosure}")
                
                # Count image tags in description
                img_count = desc.count('<img') if desc else 0
                print(f"  Number of img tags in description: {img_count}")
                
                # Check for different images vs duplicates
                if i == 1:  # Second entry should have two different images
                    has_main_img = desc.count(image_url) if desc else 0
                    has_existing_img = desc.count(existing_image_url) if desc else 0
                    print(f"  Occurrences of main image URL: {has_main_img}")
                    print(f"  Occurrences of existing image URL: {has_existing_img}")
                    
                    # Check for the expected case - both images present
                    if has_main_img == 1 and has_existing_img == 1:
                        print("  SUCCESS: Entry contains both images as expected!")
                    # Check for duplicates of the same image
                    elif has_main_img > 1 or has_existing_img > 1:
                        has_duplicates = True
                        print("  WARNING: Entry contains duplicate copies of the same image!")
                    # Missing expected images
                    else:
                        print("  WARNING: Entry is missing one or both expected images!")
                else:  # First entry should have just one image
                    has_img = desc.count(image_url) if desc else 0
                    print(f"  Occurrences of image URL: {has_img}")
                    if has_img > 1:
                        has_duplicates = True
                        print("  WARNING: Entry contains duplicate copies of the same image!")
                    elif has_img == 1:
                        print("  SUCCESS: Entry contains exactly one image as expected!")
                
                if desc:
                    print(f"  Description excerpt: {desc[:100]}...")
            
            if has_duplicates:
                print("\nWARNING: Found duplicate copies of the same image in one or more entries!")
            else:
                print("\nSUCCESS: No duplicate copies of images detected!")

            # Count total occurrences for reference
            occurrences = content.count(image_url)
            occurrences_existing = content.count(existing_image_url)
            print(f"\nTotal occurrences in feed: Main image={occurrences}, Existing image={occurrences_existing}")
    else:
        print("Feed file was not created!")

if __name__ == "__main__":
    test_no_image_duplication()
