# Archived Fix Notes

**Note**: This document contains historical troubleshooting information from October 2025 related to now-obsolete approaches. It is kept for reference only.

---

# Fix for BunnyShield Bypass Race Condition (Historical - October 2025)

## Problem

The October 6, 2025 feed update run experienced scraping failures across most comics.

## Root Cause

The issue was a **race condition** with shared browser instances during concurrent scraping operations.

## Solution

### Phase 1: Fix Race Condition
Wrapped browser usage in locks to prevent race conditions, which made scraping serial but reliable.

### Phase 2: Browser Pool for Performance
Created a pool of 4 browsers with a semaphore to allow safe parallelization.

## Impact

**Performance Improvements**:

| Approach | Status |
|----------|--------|
| Original (buggy) | ✗ Race conditions |
| Phase 1 (serial) | ✓ Works but slow (~39 minutes) |
| Phase 2 (pool) | ✓ Fast & reliable (~10-12 minutes) |

## Note

This approach has since been superseded by more efficient scraping methods implemented in November 2025. See the current codebase for the latest implementation.
