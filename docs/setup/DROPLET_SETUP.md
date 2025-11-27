# Digital Ocean Droplet Setup Guide

Complete guide for setting up ComicCaster on a Digital Ocean droplet.

## Prerequisites

- Digital Ocean account
- GitHub account with SSH access
- Your Comics Kingdom credentials

---

## Step 1: Create the Droplet

1. Go to [Digital Ocean](https://www.digitalocean.com/)
2. Create a new Droplet:
   - **Image:** Ubuntu 22.04 LTS
   - **Plan:** Basic ($6/month)
   - **Size:** 1GB RAM / 1 vCPU / 25GB SSD
   - **Datacenter:** Choose closest to you (or US East for fastest GitHub access)
   - **Authentication:** SSH key (recommended) or password
   - **Hostname:** `comiccaster-1`

3. Wait for droplet to be created (~1 minute)
4. Note the IP address

---

## Step 2: Initial Server Setup

SSH into your droplet:

```bash
ssh root@YOUR_DROPLET_IP
```

### Update system and install dependencies:

```bash
# Update package list
apt update && apt upgrade -y

# Install required packages
apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  git \
  chromium-browser \
  chromium-chromedriver \
  curl \
  vim

# Verify installations
python3 --version  # Should be 3.10+
chromium-browser --version
chromedriver --version
```

---

## Step 3: Set Up Git Authentication

### Create SSH key for GitHub:

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "comiccaster-bot@yourdomain.com"
# Press Enter to accept defaults (no passphrase needed for automation)

# Display the public key
cat ~/.ssh/id_ed25519.pub
```

### Add to GitHub:

1. Copy the SSH key output
2. Go to GitHub → Your repo → Settings → Deploy keys
3. Click "Add deploy key"
4. Title: `ComicCaster Droplet`
5. Paste the key
6. ✅ Check "Allow write access"
7. Click "Add key"

### Configure Git:

```bash
git config --global user.name "ComicCaster Bot"
git config --global user.email "comiccaster-bot@yourdomain.com"
```

---

## Step 4: Clone Repository and Install Dependencies

```bash
# Clone your repo
cd /root
git clone git@github.com:adamprime/comiccaster.git
cd comiccaster

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Verify installations
python -c "import selenium; print('Selenium:', selenium.__version__)"
python -c "from feedgen.feed import FeedGenerator; print('Feedgen: OK')"
```

---

## Step 5: Set Up Environment Variables

Create environment file:

```bash
vim ~/.comiccaster_env
```

Add your credentials (replace with real values):

```bash
# GoComics Authentication
export GOCOMICS_EMAIL="your-gocomics-email@example.com"
export GOCOMICS_PASSWORD="your-gocomics-password"

# Comics Kingdom Authentication
export COMICSKINGDOM_USERNAME="your-comicskingdom-email@example.com"
export COMICSKINGDOM_PASSWORD="your-comicskingdom-password"
export COMICSKINGDOM_COOKIE_FILE="/root/comiccaster/data/comicskingdom_cookies.pkl"

# Custom pages (if you have them)
export CUSTOM_PAGE_1=""
export CUSTOM_PAGE_2=""
export CUSTOM_PAGE_3=""
export CUSTOM_PAGE_4=""
export CUSTOM_PAGE_5=""
export CUSTOM_PAGE_6=""
```

Make it readable only by root:

```bash
chmod 600 ~/.comiccaster_env
```

Load environment variables on login:

```bash
echo "source ~/.comiccaster_env" >> ~/.bashrc
source ~/.bashrc
```

---

## Step 6: Initial Authentication

### Authenticate Comics Kingdom (One-Time):

You need to do this ONCE locally on your Mac to get cookies, then copy them to the droplet:

**On your Mac:**
```bash
cd /Users/adam/coding/rss-comics
source SETUP_COMICSKINGDOM_AUTH_LOCAL.sh  # or set env vars
python3 scripts/reauth_comicskingdom.py
# Solve reCAPTCHA when prompted
```

**Copy cookies to droplet:**
```bash
# On your Mac
cd /Users/adam/coding/rss-comics
scp data/comicskingdom_cookies.pkl root@YOUR_DROPLET_IP:/root/comiccaster/data/
```

**On the droplet, verify:**
```bash
ls -lh /root/comiccaster/data/comicskingdom_cookies.pkl
```

---

## Step 7: Test Each Scraper

Test everything manually before setting up cron:

```bash
cd /root/comiccaster
source venv/bin/activate
source ~/.comiccaster_env

# Test GoComics scraper
echo "Testing GoComics..."
python authenticated_scraper_secure.py --output-dir ./data
ls -lh data/*gocomics*.json

# Test Comics Kingdom scraper
echo "Testing Comics Kingdom..."
python comicskingdom_scraper_secure.py --output-dir ./data
ls -lh data/comicskingdom_*.json

# Test feed generation
echo "Testing feed generation..."
python scripts/update_feeds.py
python scripts/generate_comicskingdom_feeds.py
ls -lh public/feeds/ | head -20
```

If all tests pass, you're ready for automation!

---

## Step 8: Create Daily Update Script

The script is already in your repo at `scripts/droplet_daily_update.py`.

Test it manually:

```bash
cd /root/comiccaster
source venv/bin/activate
python scripts/droplet_daily_update.py
```

You should see:
- GoComics scraping progress
- Comics Kingdom scraping progress
- Feed generation
- Git commit and push
- Success message

---

## Step 9: Set Up Cron Job

Edit crontab:

```bash
crontab -e
```

Add this line (runs daily at 9 AM UTC):

```bash
# ComicCaster daily update - 9 AM UTC (4 AM EST / 5 AM EDT)
0 9 * * * /root/comiccaster/scripts/droplet_cron.sh >> /var/log/comiccaster.log 2>&1
```

Save and exit.

Verify cron is set up:

```bash
crontab -l
```

---

## Step 10: Set Up Logging

Create log rotation:

```bash
vim /etc/logrotate.d/comiccaster
```

Add:

```
/var/log/comiccaster.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

Create initial log file:

```bash
touch /var/log/comiccaster.log
chmod 644 /var/log/comiccaster.log
```

---

## Step 11: Monitoring and Maintenance

### View logs:

```bash
# View latest run
tail -100 /var/log/comiccaster.log

# Follow logs in real-time
tail -f /var/log/comiccaster.log

# Search for errors
grep -i error /var/log/comiccaster.log
```

### Manual run:

```bash
cd /root/comiccaster
source venv/bin/activate
source ~/.comiccaster_env
python scripts/droplet_daily_update.py
```

### Update code:

```bash
cd /root/comiccaster
git pull
source venv/bin/activate
pip install -r requirements.txt
```

### Re-authenticate Comics Kingdom (every ~60 days):

When cookies expire, you'll see auth failures in logs. Re-run authentication on your Mac and copy cookies:

```bash
# On Mac: Solve reCAPTCHA
python3 scripts/reauth_comicskingdom.py

# Copy to droplet
scp data/comicskingdom_cookies.pkl root@YOUR_DROPLET_IP:/root/comiccaster/data/
```

---

## Step 12: Update GitHub Actions (Optional)

You can either:

**Option A: Disable GitHub Actions** (simplest)
- The droplet now handles everything
- Can delete `.github/workflows/update-feeds.yml`

**Option B: Keep as Backup**
- Droplet runs daily at 9 AM UTC
- GitHub Actions runs as failover (if droplet fails)

---

## Troubleshooting

### Chrome/Selenium Issues:

```bash
# Check Chrome is installed
chromium-browser --version

# Check ChromeDriver
chromedriver --version

# Test Selenium
python3 -c "from selenium import webdriver; driver = webdriver.Chrome(); print('OK')"
```

### Git Push Fails:

```bash
# Check SSH key
ssh -T git@github.com

# Re-add deploy key if needed
cat ~/.ssh/id_ed25519.pub
```

### Out of Memory:

```bash
# Check memory usage
free -h

# If low, upgrade to $12/month droplet (2GB RAM)
```

### Comics Kingdom Auth Fails:

```bash
# Check cookie file exists
ls -lh /root/comiccaster/data/comicskingdom_cookies.pkl

# Check age (should be < 60 days)
stat /root/comiccaster/data/comicskingdom_cookies.pkl

# Re-authenticate if expired
```

---

## Security Notes

1. **Firewall:** Only SSH (port 22) needs to be open
2. **SSH Keys:** Use SSH keys, not passwords
3. **Credentials:** Stored in `~/.comiccaster_env` (chmod 600)
4. **Updates:** Run `apt update && apt upgrade` monthly
5. **Backups:** Not needed - everything is in GitHub

---

## Monthly Maintenance Checklist

- [ ] Check logs for errors: `tail -100 /var/log/comiccaster.log`
- [ ] Update system: `apt update && apt upgrade -y`
- [ ] Update Python packages: `pip install --upgrade -r requirements.txt`
- [ ] Check cookie expiration (~60 days)
- [ ] Verify feeds are updating: Check website

---

## Cost Summary

- **Droplet:** $6/month
- **Bandwidth:** Included (1TB/month - way more than needed)
- **Backups:** Optional ($1.20/month if desired)
- **Total:** $6-7/month = $72-84/year

---

## Next Steps

After setup is complete:

1. Monitor first 3 days to ensure reliability
2. Update README with new architecture
3. Consider adding monitoring (UptimeRobot, etc.)
4. Add all 133 Comics Kingdom comics if desired

---

**Setup Time:** 30-45 minutes
**Maintenance:** 10 minutes/month
**Reliability:** 99%+ uptime with dedicated resources
