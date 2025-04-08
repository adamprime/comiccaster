#!/usr/bin/env python3
"""
Test script for the Feed Generator Module
"""

import json
from datetime import datetime, timedelta
from comiccaster.feed_generator import ComicFeedGenerator
from comiccaster.scraper import ComicScraper

def main():
    # Create instances
    generator = ComicFeedGenerator()
    scraper = ComicScraper()
    
    try:
        # Load the comics list
        with open('comics_list.json', 'r') as f:
            comics = json.load(f)
        
        # Test with a few popular comics
        test_comics = [
            'garfield',  # Garfield
            'peanuts',   # Peanuts
            'calvinandhobbes'  # Calvin and Hobbes
        ]
        
        print("\nTesting feed generation:")
        for slug in test_comics:
            # Find comic info
            comic_info = next((c for c in comics if c['slug'] == slug), None)
            if not comic_info:
                print(f"\nComic {slug} not found in comics list")
                continue
            
            print(f"\nGenerating feed for {comic_info['name']}...")
            
            # Scrape latest comic
            metadata = scraper.scrape_comic(slug)
            if not metadata:
                print("Failed to scrape comic")
                continue
            
            # Update feed
            success = generator.update_feed(comic_info, metadata)
            if success:
                print(f"Successfully updated feed at feeds/{slug}.xml")
            else:
                print("Failed to update feed")
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    main() 