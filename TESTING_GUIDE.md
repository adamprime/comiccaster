# Testing Guide

This guide documents the testing approach for ComicCaster.

## Running Tests

### All Tests
```bash
source .venv/bin/activate
pytest -v
```

### With Coverage
```bash
pytest -v --cov=comiccaster --cov-report=term-missing
```

### Specific Test Files
```bash
pytest -v tests/test_tinyview_scraper.py
pytest -v tests/test_gocomics_scraper.py
```

## Regression Tests

### GoComics Regression Test
Ensures existing GoComics functionality continues working:
```bash
python scripts/test_gocomics_regression.py
```

Tests:
- Daily comics (Garfield, Calvin and Hobbes, Peanuts)
- Political comics (Doonesbury, Non Sequitur)
- Feed generation

### TinyView Scraper Test
Interactive testing for TinyView comics:
```bash
python scripts/test_tinyview_scraper.py --known  # Test known working comics
python scripts/test_tinyview_scraper.py --comic adhdinos  # Test specific comic
```

## Test Structure

### Unit Tests
- `test_base_scraper.py` - Abstract base class tests
- `test_gocomics_scraper.py` - GoComics scraper functionality
- `test_tinyview_scraper.py` - TinyView scraper functionality
- `test_feed_generator.py` - RSS feed generation
- `test_multi_image_rss.py` - Multi-image RSS support

### Integration Tests
- `test_scraper_factory.py` - Scraper selection logic
- `test_comic_config.py` - Comic configuration and source handling
- `test_feed_aggregator.py` - Feed aggregation functionality

## Known Test Issues

Some tests may fail due to:
1. Module import issues in test environment
2. Mock setup for Selenium WebDriver
3. Date/time dependent tests

The key regression tests (`test_gocomics_regression.py`) should always pass to ensure core functionality is maintained.