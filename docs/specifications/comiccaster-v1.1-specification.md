# ComicCaster v1.1 Specification
## Political Comics Integration

### Version Overview
ComicCaster v1.1 adds support for political editorial cartoons from GoComics, introducing a tabbed interface to separate daily syndicated comics from political cartoons. This specification follows Test-Driven Development (TDD) principles throughout.

### Executive Summary
- Add 63+ political cartoonists from GoComics
- Implement tabbed UI to separate comic types
- Handle variable publishing schedules (daily to weekly)
- Maintain backward compatibility with existing feeds
- Zero downtime deployment

---

## Architecture Changes

### Data Model Updates
1. **New File**: `political_comics_list.json` - Separate configuration for political comics
2. **Updated**: Feed generation to handle variable publishing schedules
3. **Updated**: UI to support tabbed navigation
4. **New**: Publishing frequency metadata per comic

### Component Updates
- `scripts/update_feeds.py` - Extended to process political comics with smart scheduling
- `public/index.html` - Tabbed interface implementation for both browsing and OPML generation
- `functions/generate-opml.js` - Type-specific OPML generation (separate files for daily/political)
- New test suites for all components

### Design Decision: Separate OPML Files by Type
- Users organize feeds by category naturally
- Simpler implementation and testing
- Clearer user experience with consistent tabbing
- Prevents confusion about mixed-type bundles

---

## Epic 1: Political Comics Discovery & Configuration
**Goal**: Create automated discovery and configuration system for political comics

### 1.1 Political Comics Scraper (TDD)
**Red Phase - Write Tests First**:
```python
# tests/test_political_comics_discovery.py
def test_fetch_political_comics_list():
    """Test fetching the A-Z political comics list"""
    # Should return list of 63+ comics with metadata
    
def test_extract_comic_metadata():
    """Test extracting name, author, slug from listing"""
    # Should parse HTML and return structured data
    
def test_handle_discovery_errors():
    """Test error handling for network/parsing failures"""
    # Should gracefully handle failures
```

**Green Phase - Implementation**:
- Create `scripts/discover_political_comics.py`
- Fetch https://www.gocomics.com/political-cartoons/political-a-to-z
- Parse comic listings and extract metadata
- Generate `political_comics_list.json`

**Refactor Phase**:
- Extract common scraping utilities
- Add retry logic and error handling
- Optimize parsing performance

### 1.2 Publishing Schedule Analyzer (TDD)
**Red Phase - Write Tests First**:
```python
# tests/test_publishing_analyzer.py
def test_analyze_daily_publisher():
    """Test detecting daily publishing schedule"""
    
def test_analyze_weekly_publisher():
    """Test detecting weekly publishing schedule"""
    
def test_analyze_irregular_publisher():
    """Test handling irregular schedules"""
```

**Green Phase - Implementation**:
- Create `scripts/analyze_publishing_schedule.py`
- Sample last 30 days of each comic
- Categorize as: daily, weekdays, semi-weekly, weekly, irregular
- Add `publishing_frequency` field to comics config

**Refactor Phase**:
- Create reusable schedule detection algorithms
- Add confidence scoring for schedule detection

---

## Epic 2: Feed Generation Updates
**Goal**: Extend feed generation to handle variable publishing schedules

### 2.1 Smart Update Strategy (TDD)
**Red Phase - Write Tests First**:
```python
# tests/test_smart_updates.py
def test_daily_comic_update_frequency():
    """Daily comics should update every 24 hours"""
    
def test_weekly_comic_update_frequency():
    """Weekly comics should update intelligently"""
    
def test_skip_unchanged_comics():
    """Don't regenerate feeds without new content"""
```

**Green Phase - Implementation**:
- Extend `scripts/update_feeds.py` with schedule awareness
- Implement last-published tracking
- Add smart backoff for irregular publishers

**Refactor Phase**:
- Extract update strategy to separate module
- Add configuration for update frequencies

### 2.2 Feed Content Adjustments (TDD)
**Red Phase - Write Tests First**:
```python
# tests/test_political_feed_content.py
def test_political_feed_item_count():
    """Political feeds should show last 10-15 items"""
    
def test_handle_publishing_gaps():
    """Gaps in publishing should be preserved"""
    
def test_feed_validation():
    """Generated feeds should validate as RSS 2.0"""
```

**Green Phase - Implementation**:
- Modify feed generation for political comics
- Adjust item counts based on publishing frequency
- Preserve natural publishing gaps

**Refactor Phase**:
- Create feed generation strategies per comic type
- Optimize feed file sizes

---

## Epic 3: Frontend UI Implementation
**Goal**: Implement tabbed interface for comic type separation

### 3.1 Tab Component Development (TDD)
**Red Phase - Write Tests First**:
```javascript
// tests/ui/tabs.test.js
describe('Comic Type Tabs', () => {
  test('renders daily comics tab by default');
  test('switches to political cartoons on click');
  test('preserves search state between tabs');
  test('updates URL for deep linking');
});
```

**Green Phase - Implementation**:
- Add tab HTML structure to `public/index.html`
- Implement tab switching logic
- Update comic list rendering per tab

**Refactor Phase**:
- Extract tab component for reusability
- Add keyboard navigation support

### 3.2 Comic List Filtering (TDD)
**Red Phase - Write Tests First**:
```javascript
// tests/ui/comic-list.test.js
describe('Comic List Display', () => {
  test('shows only daily comics in daily tab');
  test('shows only political comics in political tab');
  test('search filters within active tab only');
  test('comic counts update per tab');
});
```

**Green Phase - Implementation**:
- Load both `comics_list.json` and `political_comics_list.json`
- Filter display based on active tab
- Update search to respect tab context

**Refactor Phase**:
- Optimize list rendering performance
- Add lazy loading for large lists

---

## Epic 4: OPML Generation Updates
**Goal**: Implement tabbed OPML generation with type-specific bundles

### 4.1 Tabbed OPML Interface (TDD)
**Red Phase - Write Tests First**:
```javascript
// tests/functions/opml-generation.test.js
describe('OPML Tab Separation', () => {
  test('daily comics tab generates daily-only OPML');
  test('political cartoons tab generates political-only OPML');
  test('selections do not persist between tabs');
  test('OPML filename indicates comic type');
});
```

**Green Phase - Implementation**:
- Add tabs to OPML generation section
- Separate selection state per tab
- Update `functions/generate-opml.js` to accept comic type
- Generate type-specific OPML files (e.g., `daily-comics.opml`, `political-cartoons.opml`)

**Refactor Phase**:
- Share tab component with browse section
- Optimize selection state management

---

## Epic 5: Integration Testing & Deployment
**Goal**: Ensure system stability and zero-downtime deployment

### 5.1 End-to-End Testing (TDD)
**Red Phase - Write Tests First**:
```python
# tests/test_e2e_political_comics.py
def test_political_comic_discovery_to_feed():
    """Full workflow from discovery to feed generation"""
    
def test_ui_tab_interaction():
    """Test tab switching and filtering"""
    
def test_backwards_compatibility():
    """Existing feeds continue to work"""
```

**Green Phase - Implementation**:
- Create comprehensive E2E test suite
- Test full workflow scenarios
- Verify backward compatibility

### 5.2 Migration & Deployment Plan
**Tasks**:
1. Create migration script for initial political comics setup
2. Update GitHub Actions workflow
3. Test deployment in staging environment
4. Create rollback plan
5. Deploy with monitoring

---

## Testing Strategy

### Unit Tests
- Every new function must have tests written first
- Aim for 90%+ code coverage
- Mock external dependencies (GoComics API)

### Integration Tests
- Test component interactions
- Verify data flow between systems
- Test error propagation

### E2E Tests
- Full user workflows
- Cross-browser testing for UI changes
- Performance benchmarks

### Test Execution
```bash
# Run all tests
pytest -v

# Run with coverage
pytest -v --cov=comiccaster --cov-report=term-missing

# Run specific test suite
pytest -v tests/test_political_comics_discovery.py
```

---

## Development Workflow

### For Each Task:
1. **Red**: Write failing tests that define expected behavior
2. **Green**: Write minimal code to make tests pass
3. **Refactor**: Improve code quality while keeping tests green
4. **Document**: Update relevant documentation
5. **Review**: Code review focusing on test coverage

### Git Workflow
- Feature branches: `feature/v1.1-political-comics-{epic}`
- Commit message format: `test: add tests for {feature}` → `feat: implement {feature}` → `refactor: improve {feature}`
- PR requires all tests passing

---

## Success Criteria

1. **Functionality**
   - ✓ All 63+ political comics have working RSS feeds
   - ✓ Tabbed UI allows easy navigation between comic types
   - ✓ Smart update scheduling reduces unnecessary processing
   - ✓ OPML generation has separate tabs for each comic type

2. **Quality**
   - ✓ 90%+ test coverage for new code
   - ✓ All tests passing in CI/CD
   - ✓ No regression in existing functionality
   - ✓ Performance metrics maintained or improved

3. **User Experience**
   - ✓ Clear separation between comic types
   - ✓ Intuitive tab navigation
   - ✓ Existing RSS subscribers unaffected
   - ✓ Fast page load times maintained

---

## Timeline Estimate

- **Epic 1**: Political Comics Discovery - 2 days
- **Epic 2**: Feed Generation Updates - 3 days
- **Epic 3**: Frontend UI Implementation - 2 days
- **Epic 4**: OPML Generation Updates - 1 day
- **Epic 5**: Integration Testing & Deployment - 2 days

**Total**: ~10 development days

---

## Risk Mitigation

1. **GoComics Structure Changes**
   - Mitigation: Comprehensive error handling and monitoring
   - Fallback: Manual comic list maintenance

2. **Performance Impact**
   - Mitigation: Smart scheduling and caching
   - Monitoring: Track feed generation times

3. **Backward Compatibility**
   - Mitigation: Extensive testing of existing feeds
   - Rollback: Feature flag for gradual rollout

---

## Appendix: File Structure Changes

```
comiccaster/
├── political_comics_list.json      # NEW: Political comics configuration
├── scripts/
│   ├── discover_political_comics.py # NEW: Auto-discovery script
│   ├── analyze_publishing_schedule.py # NEW: Schedule analyzer
│   └── update_feeds.py             # UPDATED: Smart scheduling
├── tests/
│   ├── test_political_comics_discovery.py # NEW
│   ├── test_publishing_analyzer.py # NEW
│   ├── test_smart_updates.py      # NEW
│   ├── test_political_feed_content.py # NEW
│   └── ui/                         # NEW: Frontend tests
│       ├── tabs.test.js
│       └── comic-list.test.js
└── public/
    └── index.html                  # UPDATED: Tabbed interface
```