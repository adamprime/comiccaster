#!/usr/bin/env python3
"""
Political Comics Discovery Script
Discovers political cartoons from GoComics and generates configuration.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from comiccaster.http_client import ComicHTTPClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PoliticalComicsDiscoverer:
    """Discovers political comics from GoComics political cartoons page."""
    
    def __init__(self, base_url: str = "https://www.gocomics.com"):
        self.base_url = base_url
        self.political_comics_url = f"{base_url}/political-cartoons/political-a-to-z"
        self.client = ComicHTTPClient(base_url)
    
    def fetch_comics_list(self) -> List[Dict[str, any]]:
        """Fetch the A-Z political comics list from GoComics."""
        try:
            logger.info(f"Fetching political comics from {self.political_comics_url}")
            response = self.client.get(self.political_comics_url)
            if not response:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            comics = []
            
            # First try to find JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    if script.string:
                        data = json.loads(script.string)
                        if data.get('@type') == 'ItemList' and 'itemListElement' in data:
                            for item in data['itemListElement']:
                                if item.get('@type') == 'ListItem':
                                    comics.append({
                                        'name': item.get('name', ''),
                                        'slug': item.get('url', '').split('/')[-1],
                                        'url': item.get('url', ''),
                                        'author': item.get('name', ''),  # Default to name
                                        'position': item.get('position', len(comics) + 1),
                                        'is_political': True,
                                        'publishing_frequency': None
                                    })
                except Exception as e:
                    logger.debug(f"Error parsing JSON-LD: {e}")
            
            # Fallback to HTML parsing if no JSON-LD found
            if not comics:
                # Try different selectors based on the actual HTML structure
                selectors = ['div.gc-blended-link a', 'a.gc-feature-link', '.feature-item a']
                
                for selector in selectors:
                    links = soup.select(selector)
                    if links:
                        for position, link in enumerate(links, 1):
                            if link.get('href'):
                                metadata = self.extract_comic_metadata(link, position)
                                if metadata:
                                    comics.append(metadata)
                        break
            
            logger.info(f"Found {len(comics)} political comics")
            return comics
            
        except Exception as e:
            logger.error(f"Error fetching comics list: {e}")
            return []
    
    def extract_comic_metadata(self, link_element, position: int) -> Optional[Dict[str, any]]:
        """Extract metadata from a comic link element."""
        try:
            # Handle both BeautifulSoup elements and string input (for testing)
            if isinstance(link_element, str):
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(link_element, 'html.parser')
                link_element = soup.find('a')
                if not link_element:
                    return None
            
            href = link_element.get('href', '')
            name = link_element.get_text(strip=True)
            
            if not self.validate_url(href):
                return None
            
            # Extract slug from URL
            slug = href.strip('/').split('/')[-1]
            
            return {
                'name': name,
                'slug': slug,
                'url': urljoin(self.base_url, href),
                'author': name,  # Default to name, can be refined later
                'position': position,
                'is_political': True,
                'publishing_frequency': None  # To be determined by analyzer
            }
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return None
    
    def validate_url(self, url: str) -> bool:
        """Validate that the URL is a valid comic URL."""
        if not url:
            return False
        
        # Reject empty, anchor-only, or JavaScript URLs
        if url in ['', '#'] or url.startswith('javascript:'):
            return False
        
        # Reject external URLs
        if url.startswith('http://') or url.startswith('https://'):
            return False
        
        # Valid comic URLs should start with /
        return url.startswith('/')
    
    def deduplicate_comics(self, comics: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Remove duplicate comics based on slug."""
        seen_slugs = set()
        deduped = []
        
        for comic in comics:
            if comic['slug'] not in seen_slugs:
                seen_slugs.add(comic['slug'])
                deduped.append(comic)
        
        return deduped
    
    def save_comics_list(self, comics: List[Dict[str, any]], output_path: Path):
        """Save the comics list to a JSON file."""
        try:
            # Ensure comics are deduplicated
            comics = self.deduplicate_comics(comics)
            
            # Sort by position
            comics.sort(key=lambda x: x['position'])
            
            # Save to file
            with open(output_path, 'w') as f:
                json.dump(comics, f, indent=2)
            
            logger.info(f"Saved {len(comics)} comics to {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving comics list: {e}")
            raise


def main():
    """Main function to discover political comics."""
    discoverer = PoliticalComicsDiscoverer()
    
    # Fetch comics
    comics = discoverer.fetch_comics_list()
    
    if comics:
        # Save to political_comics_list.json
        output_path = Path('political_comics_list.json')
        discoverer.save_comics_list(comics, output_path)
        
        logger.info(f"Successfully discovered {len(comics)} political comics")
    else:
        logger.error("No comics discovered")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())