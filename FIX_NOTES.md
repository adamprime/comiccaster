# Fix for BunnyShield Bypass Race Condition

## Problem

The October 6, 2025 feed update run (action #18287841526) failed to scrape almost all comics, with errors like:

```
2025-10-06 16:37:57,157 - root - ERROR - Failed to bypass BunnyShield for https://www.gocomics.com/adamathome/2025/10/04
2025-10-06 16:37:57,232 - root - ERROR - Failed to bypass BunnyShield for https://www.gocomics.com/adult-children/2025/10/04
```

Even though the scraper was correctly fetching dates including 2025/10/05 and 2025/10/06, **no comics were successfully scraped**.

## Root Cause

The issue was a **race condition** with the shared Firefox browser instance:

1. **8 concurrent threads** were all trying to use the **same browser instance**
2. The `_browser_lock` only protected **creating** the browser, not **using** it
3. Multiple threads would call `driver.get(url)` simultaneously:
   - Thread 1: `driver.get("https://gocomics.com/garfield/2025/10/06")`
   - Thread 1: `time.sleep(3)` - waiting for page to load
   - Thread 2: `driver.get("https://gocomics.com/dilbert/2025/10/06")` **← Overwrites Thread 1's page!**
   - Thread 1: Wakes up, but the page has changed - BunnyShield check fails
   - Thread 2: Also fails because Thread 3 overwrote its page

Additionally:
- The 3-second wait was too short for BunnyShield to complete consistently
- "Connection pool is full" warnings indicated threading issues

## Solution

### Phase 1: Fix Race Condition (Initial Fix)

**Wrapped the entire browser usage in a lock** to prevent race conditions:

```python
# BEFORE (incorrect):
driver = get_browser_instance()  # Only this was locked
driver.get(url)                   # Multiple threads racing here!
time.sleep(3)
page_source = driver.page_source

# AFTER Phase 1 (correct but slow):
with _browser_lock:               # Lock protects ALL browser usage
    driver = get_browser_instance()
    driver.get(url)
    time.sleep(5)                 # Increased from 3s
    page_source = driver.page_source
```

This fixed the race condition but made scraping **serial** (~39 minutes for all comics).

### Phase 2: Browser Pool for Performance (Current Implementation)

**Created a pool of 4 browsers** with a semaphore to allow safe parallelization:

```python
# Browser pool with semaphore
_browser_pool = []
_browser_pool_size = 4
_browser_semaphore = threading.Semaphore(4)

# Usage:
driver, pool_index = get_browser_from_pool()  # Blocks if all 4 in use
try:
    driver.get(url)
    time.sleep(5)
    page_source = driver.page_source
finally:
    return_browser_to_pool()  # Release for next thread
```

Changes made in `scripts/update_feeds.py`:
- Lines 123-191: Browser pool implementation with semaphore
- Lines 224-253: Updated scraping to use pool
- Lines 1015-1023: Close pool on completion

## Impact

**Performance Improvements**:

| Approach | Parallelization | Time Estimate | Status |
|----------|----------------|---------------|--------|
| Original (buggy) | 8 threads, 1 browser | Fails | ✗ Race conditions |
| Phase 1 (serial) | 1 thread, 1 browser | ~39 minutes | ✓ Works but slow |
| Phase 2 (pool) | 4 threads, 4 browsers | ~10-12 minutes | ✓ Fast & reliable |

**Memory Usage**:
- Single browser: ~500MB
- 4-browser pool: ~2GB (acceptable for GitHub Actions)

## Alternative Approaches Considered

1. **Full browser pool** (8 browsers, one per thread):
   - Pros: Maximum parallelization
   - Cons: High memory usage (~4GB), diminishing returns
   - **Not chosen**: 4 browsers provides good balance

2. **Queue-based scraping**:
   - Pros: Better resource management
   - Cons: Complex refactoring required
   - **Not chosen**: Semaphore achieves same goal more simply

3. **Dynamic wait with page checks**:
   - Pros: Potentially faster than fixed 5s wait
   - Cons: More complex, unreliable detection
   - **Not chosen**: Fixed 5s is reliable and simple

## Testing

Test that concurrent scraping works:

```bash
python test_threading_fix.py
```

This should show comics being scraped sequentially without race conditions.

## Related Issues

- BunnyShield CDN protection added by GoComics in October 2025
- Initial fix (commit 39b6cd71b) added Selenium but didn't handle threading properly
- This fix completes the BunnyShield bypass implementation
