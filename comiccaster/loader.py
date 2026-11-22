"""
Comic list loader.

Reads a comic list (`public/*comics_list.json`) for the local Flask interface.
The pipeline's scrapers and generators read their lists themselves.
"""

import json
import logging
from typing import List, Dict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComicsLoader:
    """Loads comic lists from the JSON files in `public/`."""

    def load_comics_from_file(self, file_path: str = "public/comics_list.json") -> List[Dict[str, str]]:
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
