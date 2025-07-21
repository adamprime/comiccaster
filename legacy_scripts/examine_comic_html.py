#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import sys
import json

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

def get_comic_data(url):
    """
    Fetch and analyze a GoComics page to extract image data.
    """
    print(f"Fetching URL: {url}")
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Check for picture elements
        picture_elements = soup.find_all("picture")
        print(f"\n=== Picture Elements ({len(picture_elements)}) ===")
        for i, pic in enumerate(picture_elements):
            print(f"\n--- Picture Element #{i+1} ---")
            print(pic.prettify())
            
            # Check for source elements
            sources = pic.find_all("source")
            for j, source in enumerate(sources):
                print(f"Source #{j+1} srcset: {source.get('srcset', 'None')}")
            
            # Check for img elements
            img = pic.find("img")
            if img:
                print(f"Img src: {img.get('src', 'None')}")
                print(f"Img data-srcset: {img.get('data-srcset', 'None')}")
        
        # Check for img elements with class feature-image
        feature_images = soup.find_all("img", class_="feature-image")
        print(f"\n=== Feature Images ({len(feature_images)}) ===")
        for i, img in enumerate(feature_images):
            print(f"\n--- Feature Image #{i+1} ---")
            print(img.prettify())
            print(f"Src: {img.get('src', 'None')}")
        
        # Check for divs with class comic
        comic_divs = soup.find_all("div", class_="comic")
        print(f"\n=== Comic Divs ({len(comic_divs)}) ===")
        for i, div in enumerate(comic_divs):
            print(f"\n--- Comic Div #{i+1} ---")
            print(div.prettify())
            
            # Find images within the div
            for j, img in enumerate(div.find_all("img")):
                print(f"Comic Div #{i+1}, Img #{j+1} src: {img.get('src', 'None')}")
                print(f"Comic Div #{i+1}, Img #{j+1} data-srcset: {img.get('data-srcset', 'None')}")
                print(f"Comic Div #{i+1}, Img #{j+1} class: {img.get('class', 'None')}")
        
        # Check for script elements with asset data
        print("\n=== Checking for Asset Data in Scripts ===")
        scripts = soup.find_all("script")
        for script in scripts:
            script_text = script.string if script.string else ""
            if "asset" in script_text.lower() and "image" in script_text.lower():
                print("\nFound potential asset data in script:")
                print(script_text[:200] + "..." if len(script_text) > 200 else script_text)
                
                # Try to extract JSON data with image URLs
                try:
                    # Look for typical patterns in JavaScript that might contain image data
                    for line in script_text.split("\n"):
                        if "src" in line and "http" in line:
                            print(f"Potential image URL line: {line.strip()}")
                except Exception as e:
                    print(f"Error parsing script content: {e}")
        
        # Check meta tags for image URLs
        print("\n=== Meta Tags with Image URLs ===")
        meta_tags = soup.find_all("meta")
        for meta in meta_tags:
            content = meta.get("content", "")
            if "image" in meta.get("property", "") and "http" in content:
                print(f"{meta.get('property')}: {content}")

    except Exception as e:
        print(f"Error: {e}")

def examine_page(url):
    print(f"Examining URL: {url}")
    response = requests.get(url, headers=get_headers())
    
    if response.status_code != 200:
        print(f"Failed to fetch page: HTTP {response.status_code}")
        return
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Look for comic container
    containers = soup.find_all('div', class_=lambda x: x and 'comic' in x.lower())
    print("\nPotential comic containers:")
    for container in containers:
        print(f"\nContainer class: {container.get('class', [])}")
        
        # Look for images
        images = container.find_all('img')
        print(f"Found {len(images)} images in this container")
        for img in images:
            print(f"\nImage details:")
            print(f"  Classes: {img.get('class', [])}")
            print(f"  Source: {img.get('src', '')}")
            print(f"  Alt text: {img.get('alt', '')}")
            
            # Print parent structure
            parent = img.parent
            parent_classes = []
            while parent and parent.name:
                if parent.get('class'):
                    parent_classes.append(f"{parent.name}: {parent.get('class')}")
                parent = parent.parent
            if parent_classes:
                print("  Parent structure:")
                for p in parent_classes:
                    print(f"    {p}")

if __name__ == "__main__":
    url = "https://www.gocomics.com/calvinandhobbes"
    if len(sys.argv) > 1:
        url = sys.argv[1]
    get_comic_data(url)
    examine_page(url) 