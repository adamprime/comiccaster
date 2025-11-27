# GitHub Secrets Setup for Comics Kingdom

## Overview

Comics Kingdom scraper uses **3 GitHub Secrets** (simpler than GoComics which needs 8+!):

1. **COMICSKINGDOM_USERNAME** - Your Comics Kingdom email
2. **COMICSKINGDOM_PASSWORD** - Your password
3. **COMICSKINGDOM_COOKIES** - Authentication cookies (base64 encoded)

Unlike GoComics, Comics Kingdom doesn't need custom page URLs because it uses the standard `/favorites` page!

---

## Setup Instructions

### Step 1: Add Basic Credentials

Go to your GitHub repo:
```
Settings → Secrets and variables → Actions → New repository secret
```

Add these secrets:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `COMICSKINGDOM_USERNAME` | Your Comics Kingdom email | `your-email@example.com` |
| `COMICSKINGDOM_PASSWORD` | Your password | `your-password-here` |

---

### Step 2: Generate and Add Cookies

**Why cookies?** This lets automated runs skip reCAPTCHA for ~60 days!

#### 2a. Authenticate Locally First

```bash
# Run re-authentication script
cd /path/to/your/repo

# Set your credentials
export COMICSKINGDOM_USERNAME="your-email@example.com"
export COMICSKINGDOM_PASSWORD="your-password-here"

# Authenticate (will open browser for reCAPTCHA)
python3 scripts/reauth_comicskingdom.py
```

This creates: `data/comicskingdom_cookies.pkl`

#### 2b. Encode Cookies for GitHub

```bash
# macOS
base64 -i data/comicskingdom_cookies.pkl | pbcopy
echo "✅ Cookies copied to clipboard!"

# Linux
base64 data/comicskingdom_cookies.pkl > /tmp/cookies_base64.txt
cat /tmp/cookies_base64.txt
echo "✅ Copy the output above"
```

#### 2c. Add Cookie Secret

1. Go to: `Settings → Secrets and variables → Actions`
2. Click: **New repository secret**
3. Name: `COMICSKINGDOM_COOKIES`
4. Value: Paste the base64 string
5. Click: **Add secret**

---

## GitHub Workflow Usage

Your workflow will use these secrets like this:

```yaml
- name: Scrape Comics Kingdom
  env:
    COMICSKINGDOM_USERNAME: ${{ secrets.COMICSKINGDOM_USERNAME }}
    COMICSKINGDOM_PASSWORD: ${{ secrets.COMICSKINGDOM_PASSWORD }}
    COMICSKINGDOM_COOKIES: ${{ secrets.COMICSKINGDOM_COOKIES }}
  run: |
    # Decode cookies
    echo "$COMICSKINGDOM_COOKIES" | base64 -d > data/comicskingdom_cookies.pkl
    
    # Run scraper (no manual intervention needed!)
    python3 comicskingdom_scraper_secure.py
```

---

## Updating Cookies (Every 60 Days)

When cookies expire, update the `COMICSKINGDOM_COOKIES` secret:

```bash
# 1. Re-authenticate locally
python3 scripts/reauth_comicskingdom.py

# 2. Encode new cookies
base64 -i data/comicskingdom_cookies.pkl | pbcopy

# 3. Update GitHub Secret
#    Go to: Settings → Secrets → Actions → COMICSKINGDOM_COOKIES → Update
```

**Set a calendar reminder every 6 weeks!**

---

## Security Checklist

✅ **Never commit these files:**
- `data/comicskingdom_cookies.pkl` (in .gitignore)
- `test_comicskingdom_*.py` (in .gitignore)
- `comicskingdom_*.html` (in .gitignore)
- `comicskingdom_*.json` (in .gitignore)
- `.env` file (in .gitignore)

✅ **Only use environment variables in code:**
- ✅ `comicskingdom_scraper_secure.py` - uses env vars
- ✅ `scripts/reauth_comicskingdom.py` - uses env vars
- ❌ Never hardcode credentials

✅ **Files safe to commit:**
- ✅ `comicskingdom_scraper_secure.py`
- ✅ `scripts/reauth_comicskingdom.py`
- ✅ `.env.example` (no real credentials)
- ✅ Documentation files

---

## Comparison: GoComics vs Comics Kingdom

| Feature | GoComics | Comics Kingdom |
|---------|----------|----------------|
| Username Secret | `GOCOMICS_EMAIL` | `COMICSKINGDOM_USERNAME` |
| Password Secret | `GOCOMICS_PASSWORD` | `COMICSKINGDOM_PASSWORD` |
| Custom Pages | `CUSTOM_PAGE_1` through `CUSTOM_PAGE_6` | ❌ Not needed! |
| Cookies | ❌ Not implemented yet | `COMICSKINGDOM_COOKIES` |
| Total Secrets | 8 | 3 ✅ |

**Comics Kingdom is simpler!** It uses the standard `/favorites` page, so no custom page URLs needed.

---

## Testing Secrets

To verify secrets are working in GitHub Actions:

```yaml
- name: Test Comics Kingdom Secrets
  env:
    COMICSKINGDOM_USERNAME: ${{ secrets.COMICSKINGDOM_USERNAME }}
    COMICSKINGDOM_PASSWORD: ${{ secrets.COMICSKINGDOM_PASSWORD }}
  run: |
    if [ -z "$COMICSKINGDOM_USERNAME" ]; then
      echo "❌ COMICSKINGDOM_USERNAME not set"
      exit 1
    fi
    
    if [ -z "$COMICSKINGDOM_PASSWORD" ]; then
      echo "❌ COMICSKINGDOM_PASSWORD not set"
      exit 1
    fi
    
    echo "✅ All Comics Kingdom secrets are set"
```

---

## Troubleshooting

### "Required environment variable COMICSKINGDOM_USERNAME is not set"

**Problem:** Secret not configured or not passed to script

**Solution:**
1. Check secret exists: Settings → Secrets → Actions
2. Check workflow passes env vars correctly
3. Check secret name matches exactly (case-sensitive)

### "Saved cookies are expired or invalid"

**Problem:** Cookies are older than 60 days

**Solution:**
1. Re-authenticate locally: `python3 scripts/reauth_comicskingdom.py`
2. Encode new cookies: `base64 data/comicskingdom_cookies.pkl`
3. Update GitHub Secret: `COMICSKINGDOM_COOKIES`

### Workflow can't decode cookies

**Problem:** Cookie secret not set or corrupted

**Solution:**
```bash
# Verify base64 encoding works locally
base64 data/comicskingdom_cookies.pkl | base64 -d > /tmp/test.pkl
diff data/comicskingdom_cookies.pkl /tmp/test.pkl
# Should show no differences
```

---

## Summary

**3 Secrets Needed:**

1. ✅ `COMICSKINGDOM_USERNAME` - Your email
2. ✅ `COMICSKINGDOM_PASSWORD` - Your password  
3. ✅ `COMICSKINGDOM_COOKIES` - Base64 encoded cookie file

**Maintenance:**
- Initial setup: 10 minutes
- Cookie refresh: Every 60 days (5 minutes)
- Calendar reminder: Set for every 6 weeks
