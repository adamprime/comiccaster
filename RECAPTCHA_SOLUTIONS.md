# reCAPTCHA Solutions for Comics Kingdom

## Problem
Comics Kingdom login requires solving reCAPTCHA, which would need daily human intervention for automated scraping.

## ✅ PRIMARY SOLUTION: Cookie Persistence

### How It Works
1. **Login ONCE manually** (solve reCAPTCHA)
2. **Save authentication cookies** to a file
3. **Reuse cookies** for all future requests
4. **Cookies typically last 30-90 days** before re-authentication needed

### Implementation

```python
from selenium import webdriver
import pickle
import os
from pathlib import Path

COOKIE_FILE = Path('data/comicskingdom_cookies.pkl')

def login_and_save_cookies(driver, email, password):
    """Login once and save cookies for future use."""
    # Navigate to login page
    driver.get("https://comicskingdom.com/login")
    
    # Fill credentials (already implemented)
    # ... fill email and password ...
    
    # Wait for manual reCAPTCHA solving
    print("⏸️  Please solve the reCAPTCHA and login...")
    input("Press ENTER after you've successfully logged in...")
    
    # Save cookies
    cookies = driver.get_cookies()
    COOKIE_FILE.parent.mkdir(exist_ok=True)
    with open(COOKIE_FILE, 'wb') as f:
        pickle.dump(cookies, f)
    
    print("✅ Cookies saved!")
    return True

def load_cookies_and_authenticate(driver):
    """Load saved cookies to skip login."""
    if not COOKIE_FILE.exists():
        print("❌ No saved cookies found. Need to login first.")
        return False
    
    # Load cookies
    with open(COOKIE_FILE, 'rb') as f:
        cookies = pickle.load(f)
    
    # Navigate to site first (required before adding cookies)
    driver.get("https://comicskingdom.com")
    
    # Add all cookies
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print(f"Warning: Could not add cookie: {e}")
    
    # Verify authentication by checking if we can access favorites
    driver.get("https://comicskingdom.com/favorites")
    time.sleep(2)
    
    if 'login' in driver.current_url:
        print("❌ Cookies expired or invalid. Need to re-authenticate.")
        return False
    
    print("✅ Authenticated with saved cookies!")
    return True

def main():
    """Main scraping function with cookie management."""
    driver = setup_driver()
    
    # Try to authenticate with saved cookies first
    if not load_cookies_and_authenticate(driver):
        # If cookies don't work, do manual login
        login_and_save_cookies(driver, EMAIL, PASSWORD)
    
    # Now we're authenticated! Proceed with scraping
    scrape_favorites_page(driver)
    
    driver.quit()
```

### Benefits
- ✅ **reCAPTCHA solved only once every 1-3 months**
- ✅ **Automated daily runs** work without intervention
- ✅ **Same approach GoComics scraper should use**
- ✅ **Simple cookie file storage**

### Cookie Expiration Handling
```python
def is_cookie_expired():
    """Check if we need to re-authenticate."""
    if not COOKIE_FILE.exists():
        return True
    
    # Check file age
    cookie_age_days = (datetime.now() - datetime.fromtimestamp(
        COOKIE_FILE.stat().st_mtime
    )).days
    
    # Re-authenticate if cookies are older than 60 days
    if cookie_age_days > 60:
        print(f"⚠️  Cookies are {cookie_age_days} days old. Recommend re-authentication.")
        return True
    
    return False
```

---

## Alternative Solution 2: Manual Intervention Alert

If cookies expire, send notification:

```python
def notify_reauth_needed():
    """Create GitHub issue when re-authentication needed."""
    # Use GitHub API to create issue
    # OR send email alert
    # OR Slack notification
    
    issue_body = """
    ⚠️ Comics Kingdom Authentication Expired
    
    The saved cookies have expired and manual re-authentication is required.
    
    To fix:
    1. Run: `python scripts/reauth_comicskingdom.py`
    2. Solve the reCAPTCHA when prompted
    3. Cookies will be saved for ~60 days
    """
    
    # Create GitHub issue
    create_github_issue(
        title="Comics Kingdom Re-authentication Required",
        body=issue_body,
        labels=["maintenance", "authentication"]
    )
```

---

## Alternative Solution 3: reCAPTCHA v3 / Invisible reCAPTCHA

Some sites use reCAPTCHA v3 which is invisible and scores traffic automatically:
- ⚠️ Comics Kingdom appears to use v2 (checkbox)
- ❌ Not applicable in this case

---

## Alternative Solution 4: Undetected ChromeDriver

Use `undetected-chromedriver` which can sometimes bypass reCAPTCHA:

```python
import undetected_chromedriver as uc

driver = uc.Chrome(options=options)
```

**Pros:**
- May bypass reCAPTCHA v3
- Works with some sites

**Cons:**
- ⚠️ Unreliable with v2 reCAPTCHA (what Comics Kingdom uses)
- ⚠️ Against Google's ToS
- ⚠️ Can lead to IP bans

**Verdict:** ❌ Not recommended

---

## Alternative Solution 5: Check for Existing RSS Feeds

**Finding:** Comics Kingdom does NOT provide official RSS feeds to subscribers
- Third-party aggregators exist but don't have authenticated access
- No official API available

**Verdict:** ❌ Not available

---

## ✅ RECOMMENDED APPROACH

**Use Cookie Persistence:**

1. **Initial Setup** (one-time):
   - Run setup script locally
   - Manually solve reCAPTCHA
   - Save cookies to encrypted file
   - Store cookies as GitHub Secret

2. **Daily Automated Runs**:
   - Load cookies from secret
   - Validate authentication
   - Scrape comics
   - If authentication fails, create GitHub issue

3. **Re-authentication** (every 60-90 days):
   - GitHub issue notifies maintainer
   - Run setup script again
   - Update GitHub Secret with new cookies

### Maintenance Frequency
- **Manual intervention needed:** Every 60-90 days
- **Automated runs:** Daily without issues
- **Typical cookie lifetime:** 30-90 days (varies by site)

This is the same approach used by many automated web scrapers and is perfectly reasonable for a personal project like this!

---

## Implementation Priority

1. ✅ **Phase 1:** Build scraper with cookie persistence
2. ✅ **Phase 2:** Test cookie lifetime (probably 30-60 days)
3. ✅ **Phase 3:** Add GitHub issue alert when cookies expire
4. ✅ **Phase 4:** Document re-authentication process

**Expected maintenance:** ~10 minutes every 2 months to solve reCAPTCHA and update cookies
