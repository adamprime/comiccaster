# Testing Guide

This guide documents the comprehensive testing approach for ComicCaster, including unit tests, integration tests, and manual testing procedures.

## Test Environment Setup

### Prerequisites
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Install test dependencies
pip install pytest pytest-cov pytest-mock
```

## Running Tests

### All Tests
```bash
pytest -v
```

### With Coverage Report
```bash
pytest -v --cov=comiccaster --cov-report=term-missing --cov-report=html
# View HTML coverage report
open htmlcov/index.html
```

### Specific Test Categories
```bash
# Run only TinyView tests
pytest -v tests/test_tinyview_scraper.py

# Run only GoComics tests
pytest -v tests/test_gocomics_scraper.py

# Run multi-image RSS tests
pytest -v tests/test_multi_image_rss.py

# Run scraper factory tests
pytest -v tests/test_scraper_factory.py
```

### Run Tests Matching a Pattern
```bash
# Run all tests related to date handling
pytest -v -k "date"

# Run all tests for multi-image support
pytest -v -k "multi_image"
```

## Test Structure

### Core Test Files

#### Unit Tests
- **`test_base_scraper.py`** - Tests for the abstract base scraper class
  - Standardized output format validation
  - Error handling mechanisms
  - Common utility methods

- **`test_gocomics_scraper.py`** - GoComics scraper tests
  - JSON-LD parsing logic
  - Date matching for daily comics vs reruns
  - Error handling for missing comics

- **`test_tinyview_scraper.py`** - TinyView scraper tests (24 tests)
  - Selenium WebDriver integration
  - Multi-strip comic handling
  - Date matching across URL segments
  - Dynamic content loading

- **`test_feed_generator.py`** - RSS feed generation tests
  - Single image backward compatibility
  - Feed metadata generation
  - Date parsing and timezone handling

- **`test_multi_image_rss.py`** - Multi-image RSS support tests
  - Multiple panel comic handling
  - HTML structure for image galleries
  - Mobile-responsive image formatting
  - Performance with many images

#### Integration Tests
- **`test_scraper_factory.py`** - Scraper factory pattern tests
  - Source-based scraper selection
  - Singleton pattern implementation
  - Performance optimization

- **`test_comic_config.py`** - Configuration management tests
  - Source field validation
  - Backward compatibility
  - Comic metadata handling

- **`test_feed_aggregator.py`** - Feed aggregation tests
  - Combined feed generation
  - OPML export functionality

## Regression Testing

### GoComics Regression Test
Ensures existing GoComics functionality continues working after changes:
```bash
python scripts/test_gocomics_regression.py
```

This test verifies:
- Daily comics still scrape correctly (Garfield, Calvin and Hobbes, Peanuts)
- Political comics work properly (Doonesbury, Non Sequitur)
- Feed generation produces valid RSS
- JSON-LD parsing handles edge cases

### TinyView Interactive Testing
Manual testing tool for TinyView comics:
```bash
# Test known working comics
python scripts/test_tinyview_scraper.py --known

# Test specific comic
python scripts/test_tinyview_scraper.py --comic adhdinos

# Test with specific date
python scripts/test_tinyview_scraper.py --comic nick-anderson --date 2025/01/17
```

## Writing New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<FeatureName>`
- Test methods: `test_<specific_behavior>`

### Example Test Structure
```python
import pytest
from unittest.mock import Mock, patch

class TestNewFeature:
    """Test cases for the new feature."""
    
    def test_normal_behavior(self):
        """Test that feature works under normal conditions."""
        # Arrange
        mock_data = {...}
        
        # Act
        result = function_under_test(mock_data)
        
        # Assert
        assert result is not None
        assert result['status'] == 'success'
    
    def test_error_handling(self):
        """Test that errors are handled gracefully."""
        with pytest.raises(ValueError):
            function_under_test(invalid_data)
```

### Mocking Guidelines
- Mock external dependencies (network calls, file I/O)
- Use realistic test data that matches production patterns
- Test both success and failure scenarios

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Every push to main branch
- All pull requests
- Daily feed update workflows

### CI Test Matrix
- Python versions: 3.9, 3.10, 3.11
- Operating System: Ubuntu 24.04
- Additional checks: Code formatting, type hints

## Performance Testing

### Feed Generation Performance
```bash
# Time feed generation for all comics
time python scripts/update_feeds.py

# Profile specific scraper
python -m cProfile -s cumulative scripts/test_tinyview_scraper.py
```

### Expected Performance Metrics
- Single comic scrape: < 2 seconds
- Full feed update (500+ comics): < 10 minutes with parallel processing
- RSS feed generation: < 100ms per feed

## Debugging Failed Tests

### Common Issues and Solutions

1. **Import Errors**
   ```bash
   # Ensure package is installed in development mode
   pip install -e .
   ```

2. **Selenium WebDriver Issues**
   ```bash
   # Install Firefox for headless testing
   # macOS
   brew install --cask firefox
   
   # Ubuntu
   sudo apt-get install firefox firefox-geckodriver
   ```

3. **Date-Related Test Failures**
   - Tests may fail if run at date boundaries
   - Use fixed dates in tests or mock datetime

4. **Network-Dependent Tests**
   - Mark with `@pytest.mark.network`
   - These are skipped in offline mode

### Verbose Test Output
```bash
# Show print statements during tests
pytest -v -s tests/test_tinyview_scraper.py

# Show full diff for assertion failures
pytest -vv tests/test_multi_image_rss.py
```

## Test Data

### Mock Data Location
- Test HTML samples: Inline in test files
- Mock comic configurations: Created in test fixtures
- Expected outputs: Defined as constants in tests

### Creating Test Fixtures
```python
@pytest.fixture
def mock_comic_config():
    """Provide standard comic configuration for tests."""
    return {
        'name': 'Test Comic',
        'slug': 'test-comic',
        'source': 'tinyview',
        'url': 'https://tinyview.com/test-comic'
    }
```

## Manual Testing Checklist

Before major releases, manually verify:

- [ ] Web interface loads correctly
- [ ] All three tabs (Daily, Political, TinyView) display comics
- [ ] Feed preview works for comics from each source
- [ ] OPML generation creates valid files
- [ ] RSS feeds validate at https://validator.w3.org/feed/
- [ ] Multi-image comics display all panels
- [ ] Mobile responsive design works properly

## Known Test Limitations

1. **External Dependencies**: Some tests require internet access and may fail if comic sites are down
2. **Selenium Tests**: Require Firefox/geckodriver installation
3. **Time-Sensitive Tests**: Some tests may fail around midnight or month boundaries
4. **Platform Differences**: File path tests may need adjustment for Windows

The test suite aims for > 80% code coverage while focusing on critical paths and error handling.