# ComicCaster v1.1.5 Specification: Tinyview Integration

## Version: 1.1.5
## Date: January 2025
## Status: Draft

---

## Executive Summary

This specification outlines the implementation of Tinyview comic support in ComicCaster, enabling users to subscribe to comics from tinyview.com alongside existing GoComics content. The implementation follows test-driven development principles and coordinates with the parallel political cartoons implementation (v1.1).

### Key Features
- Support for single and multi-image Tinyview comics
- Granular source attribution system compatible with political cartoons
- Multi-image RSS feed support without UI complexity
- Seamless integration with existing RSS feed generation
- Backward compatibility with existing feeds

### Coordination Notes
- **Political Cartoons (v1.1)**: Uses `gocomics-political` source with separate configuration
- **Daily Comics**: Existing comics use `gocomics-daily` source  
- **Tinyview Comics**: New comics use `tinyview` source
- **No UI conflicts**: Each team manages their own tab interface

---

## Architecture Overview

### Current State
- ComicCaster scrapes GoComics using Selenium
- Generates RSS feeds for individual comics
- Single image per comic strip

### Future State (v1.1.5)
- Multi-source support with granular attribution:
  - `gocomics-daily` - Regular daily comics (existing)
  - `gocomics-political` - Political cartoons (v1.1 parallel work)
  - `tinyview` - Tinyview comics (new)
- Multi-image comic support
- Source-specific scrapers with common interface
- RSS feeds handle multiple images transparently

---

## Epic 1: Backend Infrastructure for Multi-Source Support

### Story 1.1: Create Abstract Base Scraper Class
**Acceptance Criteria:**
- Abstract base class defines common interface
- Supports both single and multi-image comics
- Existing GoComics scraper inherits from base class

**Tests First:**
```python
# tests/test_base_scraper.py
def test_base_scraper_interface():
    """Test that base scraper defines required methods."""
    from comiccaster.base_scraper import BaseScraper
    assert hasattr(BaseScraper, 'scrape_comic')
    assert hasattr(BaseScraper, 'fetch_comic_page')
    assert hasattr(BaseScraper, 'extract_images')

def test_base_scraper_not_instantiable():
    """Test that base scraper cannot be instantiated directly."""
    from comiccaster.base_scraper import BaseScraper
    with pytest.raises(TypeError):
        scraper = BaseScraper()
```

**Implementation Tasks:**
1. Create `base_scraper.py` with abstract methods
2. Refactor `ComicScraper` to inherit from `BaseScraper`
3. Ensure all existing tests pass

### Story 1.2: Implement Granular Source Field in Comic Configuration
**Acceptance Criteria:**
- Comics configuration includes granular 'source' field
- Source values: `gocomics-daily`, `gocomics-political`, `tinyview`
- Default source is `gocomics-daily` for backward compatibility
- Coordinates with political cartoons team (no conflicts)

**Tests First:**
```python
# tests/test_comic_config.py
def test_comic_has_granular_source_field():
    """Test that comic config includes granular source field."""
    comic = {
        'slug': 'garfield',
        'name': 'Garfield',
        'source': 'gocomics-daily'
    }
    assert comic['source'] == 'gocomics-daily'

def test_tinyview_source_field():
    """Test Tinyview comics have correct source."""
    comic = {
        'slug': 'nick-anderson',
        'name': 'Nick Anderson',
        'source': 'tinyview'
    }
    assert comic['source'] == 'tinyview'

def test_default_source_is_gocomics_daily():
    """Test backward compatibility for comics without source."""
    from comiccaster.loader import ComicsLoader
    loader = ComicsLoader()
    comic = {'slug': 'garfield', 'name': 'Garfield'}
    normalized = loader.normalize_comic_config(comic)
    assert normalized['source'] == 'gocomics-daily'

def test_political_cartoons_compatibility():
    """Test political cartoons use separate source."""
    # Political cartoons team will use 'gocomics-political'
    # This ensures no conflicts with their implementation
    comic = {
        'slug': 'political-cartoon',
        'name': 'Political Cartoon',
        'source': 'gocomics-political'
    }
    assert comic['source'] == 'gocomics-political'
```

**Implementation Tasks:**
1. Update comic configuration normalization for granular sources
2. Add source field validation (only allow approved values)
3. Coordinate with political cartoons team on source naming
4. Update loader to handle granular source field

### Story 1.3: Create Scraper Factory
**Acceptance Criteria:**
- Factory returns appropriate scraper based on source
- Raises exception for unknown sources
- Maintains single instance per source type

**Tests First:**
```python
# tests/test_scraper_factory.py
def test_factory_returns_gocomics_scraper_for_daily():
    """Test factory returns GoComics scraper for daily comics."""
    from comiccaster.scraper_factory import ScraperFactory
    scraper = ScraperFactory.get_scraper('gocomics-daily')
    assert scraper.__class__.__name__ == 'ComicScraper'

def test_factory_returns_gocomics_scraper_for_political():
    """Test factory returns GoComics scraper for political cartoons."""
    from comiccaster.scraper_factory import ScraperFactory
    scraper = ScraperFactory.get_scraper('gocomics-political')
    assert scraper.__class__.__name__ == 'ComicScraper'

def test_factory_returns_tinyview_scraper():
    """Test factory returns Tinyview scraper for tinyview source."""
    from comiccaster.scraper_factory import ScraperFactory
    scraper = ScraperFactory.get_scraper('tinyview')
    assert scraper.__class__.__name__ == 'TinyviewScraper'

def test_factory_raises_for_unknown_source():
    """Test factory raises exception for unknown source."""
    from comiccaster.scraper_factory import ScraperFactory
    with pytest.raises(ValueError):
        ScraperFactory.get_scraper('unknown')

def test_factory_backward_compatibility():
    """Test factory handles legacy 'gocomics' source."""
    from comiccaster.scraper_factory import ScraperFactory
    # Should default to gocomics-daily
    scraper = ScraperFactory.get_scraper('gocomics')
    assert scraper.__class__.__name__ == 'ComicScraper'
```

**Implementation Tasks:**
1. Create `scraper_factory.py`
2. Implement singleton pattern for scrapers
3. Add source validation

---

## Epic 2: Tinyview Scraper Implementation

### Story 2.1: Basic Tinyview Scraper for Single Images
**Acceptance Criteria:**
- Scrapes Nick Anderson comics (single image)
- Extracts image from cdn.tinyview.com
- Returns standardized comic data structure

**Tests First:**
```python
# tests/test_tinyview_scraper.py
@pytest.mark.network
def test_scrape_single_image_comic(mock_selenium_driver):
    """Test scraping single image Tinyview comic."""
    from comiccaster.tinyview_scraper import TinyviewScraper
    
    # Mock the page source with single image
    mock_selenium_driver.page_source = '''
    <img src="https://cdn.tinyview.com/nick-anderson/2025-01-17.jpg" 
         alt="Nick Anderson cartoon">
    '''
    
    scraper = TinyviewScraper()
    result = scraper.scrape_comic('nick-anderson', '2025/01/17')
    
    assert result is not None
    assert result['image_count'] == 1
    assert 'cdn.tinyview.com' in result['images'][0]['url']
```

**Implementation Tasks:**
1. Implement basic Tinyview URL construction
2. Add CDN image detection logic
3. Handle Angular page loading delays

### Story 2.2: Multi-Image Comic Support
**Acceptance Criteria:**
- Scrapes ADHDinos comics (multiple images)
- Preserves image order
- Returns all panel images

**Tests First:**
```python
@pytest.mark.network
def test_scrape_multi_image_comic(mock_selenium_driver):
    """Test scraping multi-image Tinyview comic."""
    from comiccaster.tinyview_scraper import TinyviewScraper
    
    # Mock the page source with multiple images
    mock_selenium_driver.page_source = '''
    <div class="comic-panels">
        <img src="https://cdn.tinyview.com/adhdinos/2025-01-15-1.jpg" alt="Panel 1">
        <img src="https://cdn.tinyview.com/adhdinos/2025-01-15-2.jpg" alt="Panel 2">
        <img src="https://cdn.tinyview.com/adhdinos/2025-01-15-3.jpg" alt="Panel 3">
    </div>
    '''
    
    scraper = TinyviewScraper()
    result = scraper.scrape_comic('adhdinos', '2025/01/15')
    
    assert result is not None
    assert result['image_count'] == 3
    assert all('cdn.tinyview.com' in img['url'] for img in result['images'])
```

**Implementation Tasks:**
1. Implement multi-image detection
2. Preserve panel ordering
3. Handle various gallery layouts

### Story 2.3: Error Handling and Resilience
**Acceptance Criteria:**
- Gracefully handles missing comics
- Retries on timeout
- Logs appropriate errors

**Tests First:**
```python
def test_handle_missing_comic():
    """Test graceful handling of 404 pages."""
    from comiccaster.tinyview_scraper import TinyviewScraper
    scraper = TinyviewScraper()
    result = scraper.scrape_comic('non-existent', '2025/01/17')
    assert result is None

def test_retry_on_timeout(mock_selenium_driver):
    """Test retry logic on timeout."""
    from comiccaster.tinyview_scraper import TinyviewScraper
    mock_selenium_driver.get.side_effect = [TimeoutException, None]
    
    scraper = TinyviewScraper()
    scraper.max_retries = 2
    result = scraper.scrape_comic('nick-anderson', '2025/01/17')
    
    assert mock_selenium_driver.get.call_count == 2
```

**Implementation Tasks:**
1. Add retry logic with exponential backoff
2. Implement specific error handling
3. Add comprehensive logging

---

## Epic 3: Feed Generation Enhancement

### Story 3.1: Multi-Image RSS Feed Support
**Acceptance Criteria:**
- RSS entries support multiple images
- Images displayed in order
- Mobile-friendly gallery layout

**Tests First:**
```python
# tests/test_feed_generator_multi_image.py
def test_generate_multi_image_entry():
    """Test RSS entry generation for multi-image comic."""
    from comiccaster.feed_generator import ComicFeedGenerator
    
    comic_data = {
        'title': 'ADHDinos - Test',
        'url': 'https://tinyview.com/adhdinos/2025/01/15/test',
        'images': [
            {'url': 'https://cdn.tinyview.com/1.jpg', 'alt': 'Panel 1'},
            {'url': 'https://cdn.tinyview.com/2.jpg', 'alt': 'Panel 2'}
        ],
        'published_date': datetime.now()
    }
    
    generator = ComicFeedGenerator()
    entry = generator.create_entry(comic_data)
    
    assert '<img src="https://cdn.tinyview.com/1.jpg"' in entry.content
    assert '<img src="https://cdn.tinyview.com/2.jpg"' in entry.content
    assert entry.content.index('1.jpg') < entry.content.index('2.jpg')
```

**Implementation Tasks:**
1. Update feed entry creation for multiple images
2. Add image gallery HTML template
3. Ensure backward compatibility

### Story 3.2: Source Attribution in Feeds
**Acceptance Criteria:**
- RSS entries indicate source (GoComics/Tinyview)
- Source included in feed metadata
- Maintains feed validity

**Tests First:**
```python
def test_feed_includes_source_attribution():
    """Test that feeds include source attribution."""
    from comiccaster.feed_generator import ComicFeedGenerator
    
    generator = ComicFeedGenerator()
    feed = generator.create_feed({
        'name': 'Test Comic',
        'slug': 'test',
        'source': 'tinyview'
    })
    
    feed_str = feed.rss_str()
    assert b'tinyview' in feed_str
```

**Implementation Tasks:**
1. Add source to feed metadata
2. Include source in entry categories
3. Validate feed output

---

## Epic 4: Frontend UI Enhancement

### Story 4.1: Add Tinyview Tab to Comic Browser
**Acceptance Criteria:**
- New "TinyView" tab appears in UI
- Tab shows only Tinyview comics
- Maintains existing tab functionality

**Tests First:**
```javascript
// tests/test_ui_tabs.js
describe('Comic Browser Tabs', () => {
    it('should display TinyView tab', () => {
        cy.visit('/');
        cy.get('.tab').contains('TinyView').should('be.visible');
    });
    
    it('should filter comics by source when tab clicked', () => {
        cy.visit('/');
        cy.get('.tab').contains('TinyView').click();
        cy.get('.comic-row').each(($row) => {
            cy.wrap($row).should('have.attr', 'data-source', 'tinyview');
        });
    });
});
```

**Implementation Tasks:**
1. Update index.html with new tab
2. Add JavaScript filtering logic
3. Style tab consistently

### Story 4.2: RSS Feed Preview Support for Multi-Image Comics
**Acceptance Criteria:**
- RSS feed previewer correctly displays multiple images
- Images display in correct order within feed entries
- Feed preview maintains responsive design
- No special UI indicators needed (RSS handles this transparently)

**Tests First:**
```javascript
// tests/test_feed_preview.js
it('should display all images in multi-image comic feeds', () => {
    cy.visit('/?preview=adhdinos'); // Multi-image comic
    cy.get('.feed-preview-entry').first().within(() => {
        cy.get('img').should('have.length.greaterThan', 1);
        // Images should be in order
        cy.get('img').first().should('be.visible');
        cy.get('img').last().should('be.visible');
    });
});
```

**Implementation Tasks:**
1. Ensure feed preview handles multiple images per entry
2. Test RSS compatibility with popular feed readers
3. Verify image ordering is preserved

---

## Epic 5: Testing and Quality Assurance

### Story 5.1: Integration Test Suite
**Acceptance Criteria:**
- End-to-end tests for both sources
- Performance benchmarks
- Compatibility tests

**Tests First:**
```python
# tests/test_integration.py
@pytest.mark.integration
def test_complete_workflow_gocomics():
    """Test complete workflow for GoComics."""
    # Test scraping -> feed generation -> RSS validity
    
@pytest.mark.integration
def test_complete_workflow_tinyview():
    """Test complete workflow for Tinyview."""
    # Test scraping -> feed generation -> RSS validity

def test_mixed_source_feed_generation():
    """Test generating feeds with mixed sources."""
    # Ensure both sources work together
```

### Story 5.2: Performance Testing
**Acceptance Criteria:**
- Tinyview scraping < 10 seconds per comic
- Feed generation < 1 second
- No memory leaks in Selenium

**Tests First:**
```python
@pytest.mark.performance
def test_tinyview_scraping_performance():
    """Test Tinyview scraping performance."""
    import time
    from comiccaster.tinyview_scraper import TinyviewScraper
    
    scraper = TinyviewScraper()
    start = time.time()
    scraper.scrape_comic('nick-anderson', '2025/01/17')
    duration = time.time() - start
    
    assert duration < 10, f"Scraping took {duration}s, expected < 10s"
```

---

## Deployment Strategy

### Phase 1: Beta Testing (Week 1-2)
1. Deploy to staging environment
2. Add 2-3 Tinyview comics for testing
3. Monitor error rates and performance

### Phase 2: Gradual Rollout (Week 3-4)
1. Deploy to production with feature flag
2. Enable for 10% of users initially
3. Monitor feedback and metrics

### Phase 3: Full Launch (Week 5)
1. Enable for all users
2. Add full Tinyview comic catalog
3. Update documentation

---

## Rollback Plan

If issues arise:
1. Feature flag disables Tinyview tab
2. Existing GoComics feeds unaffected
3. Database migration is reversible
4. One-command rollback: `./rollback.sh v1.1.4`

---

## Success Metrics

- Zero downtime during deployment
- < 1% error rate for new feeds
- < 10s scraping time per comic
- 95% of Tinyview comics successfully scraped daily
- User engagement with Tinyview comics > 20%

---

## Technical Debt and Future Considerations

1. Consider implementing API negotiation with Tinyview
2. Investigate caching strategies for multi-image comics
3. Plan for additional comic sources (e.g., webtoons)
4. Mobile app considerations for multi-panel display

---

## Appendices

### A. Data Structure Examples

**Single Image Comic:**
```json
{
    "slug": "nick-anderson",
    "source": "tinyview",
    "date": "2025/01/17",
    "title": "Political Commentary",
    "url": "https://tinyview.com/nick-anderson/2025/01/17/cartoon",
    "images": [
        {
            "url": "https://cdn.tinyview.com/nick-anderson/2025-01-17.jpg",
            "alt": "Nick Anderson political cartoon"
        }
    ],
    "image_count": 1
}
```

**Multi-Image Comic:**
```json
{
    "slug": "adhdinos",
    "source": "tinyview", 
    "date": "2025/01/15",
    "title": "Daily Struggles",
    "url": "https://tinyview.com/adhdinos/2025/01/15/daily-struggles",
    "images": [
        {
            "url": "https://cdn.tinyview.com/adhdinos/2025-01-15-1.jpg",
            "alt": "Panel 1: Setup"
        },
        {
            "url": "https://cdn.tinyview.com/adhdinos/2025-01-15-2.jpg",
            "alt": "Panel 2: Conflict"
        },
        {
            "url": "https://cdn.tinyview.com/adhdinos/2025-01-15-3.jpg",
            "alt": "Panel 3: Resolution"
        }
    ],
    "image_count": 3
}
```

### B. Test Coverage Requirements

- Unit tests: 90% coverage minimum
- Integration tests: All critical paths
- Performance tests: Key operations
- UI tests: User-facing changes

### C. Documentation Updates

1. Update README with Tinyview support
2. Add Tinyview section to user guide
3. Document new configuration options
4. Update API documentation

---

## Approval

- [ ] Product Owner
- [ ] Technical Lead
- [ ] QA Lead
- [ ] UX Designer

---

*End of Specification v1.1.5*