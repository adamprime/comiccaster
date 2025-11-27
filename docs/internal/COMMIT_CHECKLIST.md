# Pre-Commit Security Checklist

Run this checklist before committing any changes to the public repository.

## ✅ SAFE TO COMMIT

These files are secure and ready for public visibility:

- [x] `authenticated_scraper_secure.py` - Uses only environment variables
- [x] `.env.example` - Template with placeholders only
- [x] `.gitignore` - Updated with sensitive file patterns
- [x] `AUTHENTICATED_SCRAPING_README.md` - Generic documentation
- [x] `COMMIT_CHECKLIST.md` - This file

## ❌ NEVER COMMIT

These files contain sensitive information:

- [ ] `.env` - Your actual credentials and URLs
- [ ] `*.pkl` - Cookie/session files
- [ ] `custom_pages_config.json` - Contains account URLs
- [ ] `GITHUB_SECRETS_SETUP.md` - Contains plain text secrets
- [ ] `SECURITY_SETUP_COMPLETE.md` - Contains plain text secrets
- [ ] `AUTHENTICATED_SCRAPING_SUMMARY.md` - Contains implementation details
- [ ] `CUSTOM_PAGE_SETUP.md` - Contains URLs and setup details
- [ ] Any test scripts with hardcoded URLs or credentials
- [ ] `test_azure_b2c_login.py`
- [ ] `test_selenium_authenticated_page.py`
- [ ] `test_my_comics_page.py`
- [ ] `authenticated_custom_page_scraper.py`
- [ ] `scrape_*.py` test files
- [ ] `/tmp/*.json` output files

## 🔍 Verification Commands

Before committing, run these checks:

```bash
# Check for accidentally staged sensitive files
git status

# Search for potential secrets in staged files
git diff --cached | grep -i "User52732\|221821\|221824\|221827\|221828\|221829\|221831"

# Search for passwords or tokens
git diff --cached | grep -i "password\|token\|secret"

# Verify .env is ignored
git check-ignore .env
# Should output: .env

# Verify no pickle files are staged
git ls-files | grep "\.pkl$"
# Should output: (nothing)
```

## 📋 Pre-Commit Actions

1. **Review staged files:**
   ```bash
   git diff --cached --name-only
   ```

2. **Verify no secrets in diff:**
   ```bash
   git diff --cached
   ```

3. **Check .gitignore is working:**
   ```bash
   git status --ignored
   ```

4. **Confirm only approved files:**
   - Python code uses environment variables
   - Documentation is generic
   - No account-specific identifiers

## 🚨 If You Accidentally Commit Secrets

If secrets are accidentally committed:

1. **DO NOT push to remote**
2. **Amend or reset the commit:**
   ```bash
   git reset HEAD~1
   ```
3. **Remove sensitive files:**
   ```bash
   git rm --cached <sensitive-file>
   ```
4. **Commit again with only safe files**

If already pushed:
1. **Immediately rotate all secrets** (change passwords, create new custom pages)
2. **Contact GitHub support** to remove from history
3. **Force push cleaned history** (breaks collaborators - use carefully)

## ✅ Final Check

Before pushing:
- [ ] Reviewed all changed files
- [ ] No secrets in commit
- [ ] .gitignore working properly
- [ ] GitHub Secrets are set up
- [ ] Local .env file exists and is ignored
- [ ] Documentation is generic

## 🎯 Remember

**Golden Rule:** If you're unsure whether a file contains sensitive info, DON'T commit it.

**When in doubt:**
1. Check the file for account-specific URLs
2. Check for usernames, passwords, or tokens
3. Check for detailed technical implementation that could aid attackers
4. If any of above - DON'T COMMIT

**Safe indicators:**
- Uses `os.environ.get()` or `${VARIABLE}` placeholders
- Documentation uses "example.com" or generic descriptions
- No specific page IDs or account identifiers
