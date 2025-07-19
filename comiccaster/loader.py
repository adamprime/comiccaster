"""
Comics A-to-Z Loader Module

This module handles fetching and parsing the list of available comics from GoComics.
It extracts comic information from the JSON-LD metadata on the A-to-Z page.
"""

import json
import re
import logging
import time
import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComicsLoader:
    """Handles loading and parsing comic information from GoComics."""
    
    def __init__(self, base_url: str = "https://www.gocomics.com"):
        """
        Initialize the ComicsLoader.
        
        Args:
            base_url (str): The base URL for GoComics. Defaults to "https://www.gocomics.com".
        """
        self.base_url = base_url
        self.a_to_z_url = f"{base_url}/comics/a-to-z"
        self.comics_list = []
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        
        if 'CHROME_BIN' in os.environ:
            self.chrome_options.binary_location = os.environ['CHROME_BIN']

    def setup_driver(self):
        """Set up the Selenium WebDriver with Chrome in headless mode."""
        if os.environ.get('USE_WEBDRIVER_MANAGER', 'false').lower() == 'true':
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=self.chrome_options
            )
        else:
            service = Service()
            if 'CHROMEDRIVER_PATH' in os.environ:
                service = Service(executable_path=os.environ['CHROMEDRIVER_PATH'])
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
            
        self.driver.set_window_size(1920, 1080)
    
    def fetch_page(self) -> Optional[str]:
        """
        Fetch the A-to-Z page content using Selenium to execute JavaScript.
        
        Returns:
            Optional[str]: The HTML content of the page, or None if the request fails.
        """
        try:
            if not self.driver:
                self.setup_driver()
            
            logger.info(f"Fetching {self.a_to_z_url}")
            self.driver.get(self.a_to_z_url)
            
            # Wait for the comics list to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ol li a")))
            
            # Additional wait for any dynamic content
            time.sleep(2)
            
            # Get the page source after JavaScript execution
            html_content = self.driver.page_source
            
            # Save the raw response for debugging
            with open("debug_raw_response.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            
            return html_content
            
        except TimeoutException:
            logger.error("Timeout waiting for comics list to load")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch A-to-Z page: {e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def parse_comic_title(self, text: str) -> Tuple[str, Optional[str], bool]:
        """
        Parse a comic title to extract name, author, and update status.
        
        Args:
            text (str): The raw comic title text.
            
        Returns:
            Tuple[str, Optional[str], bool]: (comic_name, author, is_updated)
        """
        # Check if the comic is updated
        is_updated = text.endswith("Updated")
        if is_updated:
            text = text[:-7].strip()  # Remove "Updated" suffix
        
        # Split on "By" to separate comic name and author
        parts = text.split("By", 1)
        comic_name = parts[0].strip()
        author = parts[1].strip() if len(parts) > 1 else None
        
        return comic_name, author, is_updated
    
    def extract_comics_from_source(self, html_text: str) -> List[Dict[str, str]]:
        """
        Extract comic information from the page's HTML structure.
        
        Args:
            html_text (str): The HTML content of the A-to-Z page.
            
        Returns:
            List[Dict[str, str]]: List of dictionaries containing comic information.
            
        Raises:
            ValueError: If the comics list cannot be found.
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, 'html.parser')
            comic_list = []
            position = 1
            
            # Find all comic links in ordered lists
            for link in soup.select("ol li a"):
                raw_title = link.text.strip()
                url = link.get("href", "")
                
                if raw_title and url:
                    # Parse the comic title
                    name, author, is_updated = self.parse_comic_title(raw_title)
                    
                    # Make URL absolute if it's relative
                    if url.startswith("/"):
                        url = f"{self.base_url}{url}"
                    
                    # Extract the comic slug from the URL
                    slug = url.split("/")[-1]
                    
                    comic_list.append({
                        "name": name,
                        "author": author,
                        "url": url,
                        "slug": slug,
                        "position": position,
                        "is_updated": is_updated
                    })
                    position += 1
            
            if not comic_list:
                raise ValueError("No comics found in the page")
            
            logger.info(f"Successfully extracted {len(comic_list)} comics")
            return comic_list
            
        except Exception as e:
            logger.error(f"Unexpected error while extracting comics: {e}")
            raise
    
    def save_comics_list(self, comics: List[Dict[str, str]], output_file: str = "comics_list.json"):
        """
        Save the extracted comic information to a JSON file.
        
        Args:
            comics (List[Dict[str, str]]): List of comic information dictionaries.
            output_file (str): Path to the output JSON file.
        """
        try:
            # Ensure the output directory exists
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(comics, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(comics)} comics to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save comics list: {e}")
            raise
    
    def load_comics(self, save_to_file: bool = True) -> List[Dict[str, str]]:
        """
        Main method to load and optionally save the comics list.
        
        Args:
            save_to_file (bool): Whether to save the comics list to a file.
            
        Returns:
            List[Dict[str, str]]: List of comic information dictionaries.
        """
        html_content = self.fetch_page()
        if not html_content:
            raise ValueError("Failed to fetch the A-to-Z page")
        
        comics = self.extract_comics_from_source(html_content)
        
        if save_to_file:
            self.save_comics_list(comics)
        
        return comics

    def load_comics_from_file(self, file_path: str = "comics_list.json") -> List[Dict[str, str]]:
        """
        Load comic information from a JSON file.
        
        Args:
            file_path (str): Path to the JSON file containing comic information.
            
        Returns:
            List[Dict[str, str]]: List of comic information dictionaries.
            
        Raises:
            FileNotFoundError: If the file doesn't exist.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                comics = json.load(f)
            logger.info(f"Loaded {len(comics)} comics from {file_path}")
            return comics
        except FileNotFoundError:
            logger.error(f"Comics list file not found: {file_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in comics list file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load comics from file: {e}")
            raise
    
    def get_comics_list(self, file_path: str = "comics_list.json") -> List[str]:
        """
        Get a list of all comic slugs from the JSON file.
        
        Args:
            file_path (str): Path to the JSON file containing comic information.
            
        Returns:
            List[str]: List of comic slugs.
        """
        try:
            comics_data = self.load_comics_from_file(file_path)
            return [comic['slug'] for comic in comics_data]
        except Exception as e:
            logger.error(f"Failed to get comics list: {e}")
            return []
    
    def normalize_comic_config(self, comic: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize a comic configuration dictionary by adding default values.
        
        Args:
            comic (Dict[str, str]): Comic configuration dictionary.
            
        Returns:
            Dict[str, str]: Normalized comic configuration with default source.
        """
        normalized = comic.copy()
        
        # Add default source if not present (backward compatibility)
        if 'source' not in normalized:
            normalized['source'] = 'gocomics-daily'
        
        return normalized
    
    def validate_comic_config(self, comic: Dict[str, str]) -> bool:
        """
        Validate a comic configuration dictionary.
        
        Args:
            comic (Dict[str, str]): Comic configuration dictionary.
            
        Returns:
            bool: True if valid.
            
        Raises:
            ValueError: If the configuration is invalid.
        """
        # Valid source types
        valid_sources = ['gocomics-daily', 'gocomics-political', 'tinyview']
        
        # Check required fields
        required_fields = ['slug', 'name']
        for field in required_fields:
            if field not in comic:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate source field
        source = comic.get('source', 'gocomics-daily')
        if source not in valid_sources:
            raise ValueError(f"Invalid source '{source}'. Valid sources: {valid_sources}")
        
        return True
    
    def load_all_comics(self, regular_comics_file: str = "comics_list.json", 
                       political_comics_file: str = "political_comics_list.json") -> List[Dict[str, str]]:
        """
        Load all comics from both regular and political comics files.
        
        Args:
            regular_comics_file (str): Path to regular comics JSON file.
            political_comics_file (str): Path to political comics JSON file.
            
        Returns:
            List[Dict[str, str]]: List of all comic configurations with normalized sources.
        """
        all_comics = []
        
        # Load regular comics
        try:
            regular_comics = self.load_comics_from_file(regular_comics_file)
            for comic in regular_comics:
                normalized = self.normalize_comic_config(comic)
                self.validate_comic_config(normalized)
                all_comics.append(normalized)
            logger.info(f"Loaded {len(regular_comics)} regular comics")
        except FileNotFoundError:
            logger.warning(f"Regular comics file not found: {regular_comics_file}")
        except Exception as e:
            logger.error(f"Error loading regular comics: {e}")
            
        # Load political comics
        try:
            political_comics = self.load_comics_from_file(political_comics_file)
            for comic in political_comics:
                # Political comics should already have source set, but normalize anyway
                normalized = self.normalize_comic_config(comic)
                # Override source for political comics if not explicitly set to political
                if normalized.get('source') == 'gocomics-daily':
                    normalized['source'] = 'gocomics-political'
                self.validate_comic_config(normalized)
                all_comics.append(normalized)
            logger.info(f"Loaded {len(political_comics)} political comics")
        except FileNotFoundError:
            logger.info(f"Political comics file not found: {political_comics_file}")
        except Exception as e:
            logger.error(f"Error loading political comics: {e}")
        
        logger.info(f"Total comics loaded: {len(all_comics)}")
        return all_comics

def main():
    """Main function to demonstrate the ComicsLoader usage."""
    try:
        loader = ComicsLoader()
        comics = loader.load_comics()
        print(f"\nSuccessfully loaded {len(comics)} comics")
        
        # Print some sample comics
        print("\nSample comics:")
        for comic in comics[:5]:
            status = "Updated" if comic["is_updated"] else "Not Updated"
            author = f" by {comic['author']}" if comic['author'] else ""
            print(f"- {comic['name']}{author} ({status}) [{comic['slug']}]")
            
    except Exception as e:
        logger.error(f"Failed to load comics: {e}")
        raise

if __name__ == "__main__":
    main() 