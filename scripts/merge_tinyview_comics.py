#!/usr/bin/env python3
"""
Merge Tinyview comics from tinyview_comics_list.json into the main comics_list.json
"""

import json
import sys
from pathlib import Path

def main():
    # Load the Tinyview comics list
    tinyview_list_path = Path(__file__).parent.parent / 'public' / 'tinyview_comics_list.json'
    main_list_path = Path.home() / 'coding' / 'rss-comics' / 'public' / 'comics_list.json'
    
    with open(tinyview_list_path, 'r') as f:
        tinyview_comics = json.load(f)
    
    with open(main_list_path, 'r') as f:
        all_comics = json.load(f)
    
    # Find the highest position in the current list
    max_position = max(comic.get('position', 0) for comic in all_comics)
    
    # Get existing Tinyview comic slugs
    existing_tinyview = {comic['slug'] for comic in all_comics if comic.get('source') == 'tinyview'}
    
    # Add missing Tinyview comics
    added = 0
    for comic in tinyview_comics:
        if comic['slug'] not in existing_tinyview:
            max_position += 1
            all_comics.append({
                'name': comic['name'],
                'author': comic.get('author', 'Unknown'),
                'url': comic['url'],
                'slug': comic['slug'],
                'position': max_position,
                'is_updated': False,
                'source': 'tinyview'
            })
            added += 1
            print(f"Added: {comic['name']}")
    
    # Save the updated list
    with open(main_list_path, 'w') as f:
        json.dump(all_comics, f, indent=2)
    
    print(f"\nAdded {added} Tinyview comics to main comics list")
    print(f"Total comics now: {len(all_comics)}")

if __name__ == "__main__":
    main()