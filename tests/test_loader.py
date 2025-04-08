#!/usr/bin/env python3
"""
Test script for the Comics A-to-Z Loader
"""

from comiccaster.loader import ComicsLoader

def main():
    # Create a loader instance
    loader = ComicsLoader()
    
    try:
        # Load comics and save to file
        comics = loader.load_comics(save_to_file=True)
        
        # Print some sample comics
        print("\nSample comics:")
        for comic in comics[:5]:  # Show first 5 comics
            print(f"- {comic['name']} (slug: {comic['slug']})")
            
        print(f"\nTotal comics loaded: {len(comics)}")
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    main() 