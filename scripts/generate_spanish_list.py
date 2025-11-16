#!/usr/bin/env python3
"""
Generate Spanish comics list from main comics catalog.
Identifies comics by Spanish keywords in slug/name.
"""

import json
from pathlib import Path


def is_spanish_comic(comic):
    """Determine if a comic is in Spanish."""
    slug = comic.get('slug', '').lower()
    name = comic.get('name', '').lower()
    
    # Check for Spanish indicators in slug or name
    spanish_patterns = [
        'spanish', 'español', 'espanol', 'en español', 'en espanol',
        '-spa-', '-esp-', '(spanish)', '(español)'
    ]
    
    if any(pattern in slug or pattern in name for pattern in spanish_patterns):
        return True
    
    # Check for known Spanish comic titles
    spanish_titles = [
        'pepita', 'tapon', 'beto el recluta', 'daniel el travieso',
        'circulo familiar', 'olafo', 'educando', 'jeremias',
        'palurdeando', 'motas', 'tigrillo', 'quintin', 'soso y siso',
        'maldades', 'lalo y lola', 'macanudo', 'nunca falta',
        'el fantasma', 'principe valiente', 'maria de oro',
        'don abundio', 'a toda velocidad', 'solo para ninos',
        'benitin y eneas', 'baldo en', 'las hermanas stone',
        'crock spanish', 'goomer spanish', 'willy black spanish'
    ]
    
    if any(title in name for title in spanish_titles):
        return True
    
    return False


def main():
    print("Generating Spanish comics list...")
    
    # Load main comics list
    comics_file = Path('public/comics_list.json')
    with open(comics_file, 'r') as f:
        all_comics = json.load(f)
    
    print(f"Total comics: {len(all_comics)}")
    
    # Filter Spanish comics
    spanish_comics = [comic for comic in all_comics if is_spanish_comic(comic)]
    
    print(f"Spanish comics found: {len(spanish_comics)}")
    
    # Sort alphabetically by name
    spanish_comics.sort(key=lambda x: x['name'].lower())
    
    # Save to spanish_comics_list.json
    output_file = Path('public/spanish_comics_list.json')
    with open(output_file, 'w') as f:
        json.dump(spanish_comics, f, indent=2)
    
    print(f"✅ Saved {len(spanish_comics)} Spanish comics to {output_file}")
    
    # Print sample
    print("\nSample Spanish comics:")
    for comic in spanish_comics[:10]:
        print(f"  - {comic['name']} ({comic['slug']})")
    
    if len(spanish_comics) > 10:
        print(f"  ... and {len(spanish_comics) - 10} more")


if __name__ == '__main__':
    main()
