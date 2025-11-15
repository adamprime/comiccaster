#!/usr/bin/env python3
"""
Add Comics Kingdom favorites to the catalog for testing.
Uses the scraped data to add only the comics in your favorites.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict


def load_scraped_favorites(date_str: str = '2025-11-15') -> List[Dict]:
    """Load scraped Comics Kingdom favorites."""
    data_file = Path('data') / f'comicskingdom_{date_str}.json'
    
    if not data_file.exists():
        print(f"❌ Scraped data not found: {data_file}")
        print("Run the scraper first: python comicskingdom_scraper_secure.py")
        sys.exit(1)
    
    with open(data_file, 'r') as f:
        comics = json.load(f)
    
    # Filter out invalid entries
    valid_comics = []
    for comic in comics:
        slug = comic.get('slug', '')
        # Skip creator pages and malformed URLs
        if slug and slug != 'creator' and not slug.startswith('?'):
            valid_comics.append(comic)
    
    return valid_comics


def load_comics_list(file_path: Path) -> List[Dict]:
    """Load existing comics list."""
    with open(file_path, 'r') as f:
        return json.load(f)


def add_comics_to_list(existing: List[Dict], new_comics: List[Dict]) -> tuple[List[Dict], int]:
    """Add new comics to list, avoiding duplicates."""
    existing_slugs = {c['slug'] for c in existing}
    max_position = max([c.get('position', 0) for c in existing], default=0)
    
    added = 0
    for comic in new_comics:
        if comic['slug'] not in existing_slugs:
            # Add new comic
            new_entry = {
                'name': comic['name'],
                'slug': comic['slug'],
                'url': comic['url'],
                'author': '',  # Unknown for now
                'position': max_position + added + 1,
                'is_updated': False,
                'source': 'comicskingdom'
            }
            existing.append(new_entry)
            added += 1
    
    return existing, added


def main():
    """Main function."""
    print("="*80)
    print("Adding Comics Kingdom Favorites to Catalog")
    print("="*80)
    print()
    
    # Load scraped favorites
    print("Loading your Comics Kingdom favorites...")
    favorites = load_scraped_favorites()
    print(f"✅ Found {len(favorites)} favorites")
    
    # Show what we're adding
    print("\nComics to add:")
    for comic in favorites:
        print(f"  - {comic['name']} ({comic['slug']})")
    print()
    
    # Load existing daily comics list
    comics_file = Path('public/comics_list.json')
    print(f"Loading existing comics list from {comics_file}...")
    existing_comics = load_comics_list(comics_file)
    print(f"✅ Current daily comics: {len(existing_comics)}")
    print()
    
    # Add favorites to daily comics
    # (None of your favorites are political cartoons)
    print("Adding Comics Kingdom favorites to daily comics list...")
    updated_comics, added_count = add_comics_to_list(existing_comics, favorites)
    print(f"✅ Added {added_count} new comics")
    print()
    
    # Save updated list
    print("Saving updated comics list...")
    with open(comics_file, 'w') as f:
        json.dump(updated_comics, f, indent=2)
    print(f"✅ Saved to {comics_file}")
    print()
    
    print("="*80)
    print("✅ SUCCESS!")
    print("="*80)
    print(f"Total daily comics: {len(updated_comics)}")
    print(f"Comics Kingdom favorites: {added_count} added")
    print()
    print("Next steps:")
    print("  1. Visit http://localhost:8888 (or your Netlify dev server)")
    print("  2. Check the Daily Comics tab for your Comics Kingdom comics")
    print("  3. Test feed generation for these comics")
    print("="*80)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
