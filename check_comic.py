#!/usr/bin/env python3
import requests
import json
from bs4 import BeautifulSoup

def check_comic_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Print the title for identification
        title = soup.select_one('title')
        print(f'Page title: {title.text if title else "No title"}')
        
        # Check og:image
        og_image = soup.select_one('meta[property="og:image"]')
        print(f'og:image value: {og_image["content"] if og_image else "Not found"}')
        
        # Get all OG tags
        print('\nAll OG tags:')
        og_tags = {}
        for tag in soup.select('meta[property^="og:"]'):
            og_tags[tag['property']] = tag.get('content')
        
        print(json.dumps(og_tags, indent=2))
        
        # Try to find any image tags that might contain the comic
        print("\nLooking for possible comic image tags:")
        for img in soup.select('img'):
            if img.get('class') and any(cls for cls in img.get('class') if 'strip' in cls.lower() or 'comic' in cls.lower()):
                print(f"Found potential comic image: {img.get('src', 'No src')} (classes: {img.get('class')})")
            elif img.get('alt') and ('comic' in img.get('alt').lower() or 'strip' in img.get('alt').lower()):
                print(f"Found image with comic-related alt text: {img.get('src', 'No src')} (alt: {img.get('alt')})")
        
        # Look for comic container divs or sections
        print("\nLooking for comic containers:")
        for div in soup.select('div, section'):
            if div.get('class') and any(cls for cls in div.get('class') if 'comic' in cls.lower() or 'strip' in cls.lower()):
                print(f"Found potential comic container: {div.name} (classes: {div.get('class')})")
                img_inside = div.select_one('img')
                if img_inside:
                    print(f"  - Image inside: {img_inside.get('src', 'No src')}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    comics = [
        "https://www.gocomics.com/garfield/2023/04/05",  # Garfield
        "https://www.gocomics.com/calvinandhobbes/2023/04/05",  # Calvin and Hobbes
        "https://www.gocomics.com/peanuts/2023/04/05",  # Peanuts
    ]
    
    for url in comics:
        print(f"\n{'='*50}")
        print(f"Checking URL: {url}")
        print(f"{'='*50}")
        check_comic_url(url) 