# Launchd Automation Troubleshooting

## Issue: Scripts Run But Can't Push to GitHub

### What Happened

The launchd jobs (Comics Kingdom at 12:30 AM, TinyView at 12:35 AM) ran successfully and scraped comics, but failed to push to GitHub with this error:

```
failed to get: -25320
fatal: could not read Username for 'https://github.com': Device not configured
```

### Root Cause

- Launchd jobs run in the background without access to your login keychain
- The repo was using HTTPS URLs which require keychain access for credentials
- SSH authentication was already set up but not being used

### Solution Applied

**1. Switched from HTTPS to SSH:**
```bash
git remote set-url origin git@github.com:adamprime/comiccaster.git
```

**2. Added SSH key to agent with keychain:**
```bash
ssh-add --apple-use-keychain ~/.ssh/id_rsa
```

**3. Created SSH config for automatic keychain use:**
```bash
# ~/.ssh/config
Host github.com
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_rsa
```

### Verification

Run this test to verify everything works:
```bash
bash test_git_push.sh
```

Should output:
```
Testing git remote connection...
origin	git@github.com:adamprime/comiccaster.git (fetch)
origin	git@github.com:adamprime/comiccaster.git (push)

Testing SSH to GitHub...
Hi adamprime! You've successfully authenticated...

All tests passed!
```

### How It Works Now

1. **12:30 AM**: Comics Kingdom script runs
   - Scrapes comics using stored cookies
   - Commits to git
   - Pushes via SSH (no keychain needed!)
   
2. **12:35 AM**: TinyView script runs
   - Scrapes comics with Selenium
   - Commits to git
   - Pushes via SSH

3. **9:00 AM UTC** (GitHub Actions scheduled)
   - Reads Comics Kingdom & TinyView data from repo
   - Scrapes GoComics
   - Generates all feeds
   - Pushes updated feeds

### Monitoring

Check if tonight's runs worked:

```bash
# Check logs
tail -50 ~/coding/rss-comics/logs/comicskingdom_local.log
tail -50 ~/coding/rss-comics/logs/tinyview_local.log

# Check if data was pushed
ls -la ~/coding/rss-comics/data/ | grep $(date +%Y-%m-%d)

# Check git log
cd ~/coding/rss-comics && git log --oneline -5 | grep "Update"
```

### Future Troubleshooting

**If scripts still can't push:**

1. Verify SSH works:
   ```bash
   ssh -T git@github.com
   ```

2. Check SSH key is in agent:
   ```bash
   ssh-add -l
   ```

3. Re-add key if needed:
   ```bash
   ssh-add --apple-use-keychain ~/.ssh/id_rsa
   ```

4. Check launchd job status:
   ```bash
   launchctl list | grep comiccaster
   ```

5. Check logs for errors:
   ```bash
   tail -100 ~/coding/rss-comics/logs/comicskingdom_local.log
   ```

### Testing Manual Run

Test the scripts manually to see if they work:

```bash
# Test Comics Kingdom
cd ~/coding/rss-comics
bash scripts/local_comicskingdom_update.sh

# Test TinyView
bash scripts/local_tinyview_update.sh
```

Both should complete successfully and push to GitHub.
