"""Comics Kingdom's share of the two public/ catalogs.

Both the Comics Kingdom scraper and its feed generator need every
``source == "comicskingdom"`` entry from ``comics_list.json`` (the daily tab)
and ``political_comics_list.json`` (the political tab). Until 2026-09-28 each
script had its own loader, and both read only the daily list. Cartoonists listed
only on the political tab were never scraped, so their feeds 404'd. One helper
means one place to be right.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Union

logger = logging.getLogger(__name__)

DAILY_CATALOG = 'comics_list.json'
POLITICAL_CATALOG = 'political_comics_list.json'


def load_comicskingdom_catalog(catalog_dir: Union[str, Path] = 'public') -> List[Dict]:
    """Return every Comics Kingdom catalog entry, each slug once.

    Daily-catalog entries come first, then political ones. The daily catalog is
    required. A missing political catalog is logged and skipped, as the GoComics
    loader does.

    A slug listed more than once keeps its first (daily) entry and logs a
    warning. tests/test_catalog_source_integrity.py keeps the two lists apart;
    this guard turns a future slip into a warning instead of a double scrape.
    """
    catalog_dir = Path(catalog_dir)

    with open(catalog_dir / DAILY_CATALOG, 'r') as f:
        catalogs = [(DAILY_CATALOG, json.load(f))]

    political_file = catalog_dir / POLITICAL_CATALOG
    if political_file.exists():
        with open(political_file, 'r') as f:
            catalogs.append((POLITICAL_CATALOG, json.load(f)))
    else:
        logger.warning(
            f"{political_file} not found; loading Comics Kingdom comics "
            f"from {DAILY_CATALOG} only"
        )

    comics = []
    listed_in = {}  # slug -> catalog file its kept entry came from
    for catalog_name, entries in catalogs:
        for comic in entries:
            if comic.get('source') != 'comicskingdom':
                continue
            slug = comic['slug']
            if slug in listed_in:
                logger.warning(
                    f"Comics Kingdom slug '{slug}' is listed in {listed_in[slug]} "
                    f"and again in {catalog_name}; keeping the {listed_in[slug]} "
                    f"entry so it is scraped once"
                )
                continue
            listed_in[slug] = catalog_name
            comics.append(comic)

    return comics
