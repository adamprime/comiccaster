import pytest
import os
import tempfile
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

@pytest.fixture(scope="session")
def chrome_options():
    """Configure Chrome options for testing."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    if 'CHROME_BIN' in os.environ:
        options.binary_location = os.environ['CHROME_BIN']
    
    return options

@pytest.fixture(scope="session")
def chrome_service():
    """Configure ChromeDriver service."""
    if 'CHROMEDRIVER_PATH' in os.environ:
        service = Service(executable_path=os.environ['CHROMEDRIVER_PATH'])
    else:
        service = Service()
    return service

@pytest.fixture
def browser(chrome_options, chrome_service):
    """Provide a browser instance for testing."""
    driver = webdriver.Chrome(options=chrome_options, service=chrome_service)
    driver.set_window_size(1920, 1080)
    yield driver
    driver.quit()

@pytest.fixture
def test_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def sample_comics_list(test_data_dir):
    """Create a sample comics list file."""
    comics = [
        {
            "name": "Calvin and Hobbes",
            "author": "Bill Watterson",
            "url": "https://www.gocomics.com/calvinandhobbes",
            "slug": "calvinandhobbes"
        },
        {
            "name": "Peanuts",
            "author": "Charles Schulz",
            "url": "https://www.gocomics.com/peanuts",
            "slug": "peanuts"
        }
    ]
    
    comics_file = os.path.join(test_data_dir, "comics_list.json")
    with open(comics_file, "w") as f:
        json.dump(comics, f)
    return comics_file

@pytest.fixture
def mock_feed_dir(test_data_dir):
    """Create a mock feeds directory."""
    feed_dir = os.path.join(test_data_dir, "feeds")
    os.makedirs(feed_dir, exist_ok=True)
    return feed_dir

@pytest.fixture
def mock_token_dir(test_data_dir):
    """Create a mock tokens directory."""
    token_dir = os.path.join(test_data_dir, "tokens")
    os.makedirs(token_dir, exist_ok=True)
    return token_dir 