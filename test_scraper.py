#!/usr/bin/env python3
"""
Test script for the Comic Scraper Module
"""

import json
from datetime import datetime
from comiccaster.scraper import ComicScraper

def main():
    # Create a scraper instance
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
        
        print("\nTesting comic scraping:")
        for slug in test_comics:
            print(f"\nScraping {slug}...")
            metadata = scraper.scrape_comic(slug)
            
            if metadata:
                print("Success!")
                print("Metadata:")
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
            else:
                print("Failed to scrape comic")
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    main() 