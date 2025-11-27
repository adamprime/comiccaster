# Digital Ocean Droplet - Quick Start Checklist

Use this checklist while setting up your droplet. Full details in [DROPLET_SETUP.md](DROPLET_SETUP.md).

---

## ☑️ Pre-Setup (5 minutes)

- [ ] Create Digital Ocean account (if needed)
- [ ] Have GitHub SSH access ready
- [ ] Know your Comics Kingdom credentials
- [ ] Have your local repo with fresh cookies

---

## ☑️ Create Droplet (2 minutes)

- [ ] Create droplet: Ubuntu 22.04, $6/month, 1GB RAM
- [ ] Note the IP address: `___.___.___. ___`
- [ ] SSH into droplet: `ssh root@YOUR_IP`

---

## ☑️ Install Dependencies (5 minutes)

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git chromium-browser chromium-chromedriver curl vim
```

- [ ] Verify Python: `python3 --version` (should be 3.10+)
- [ ] Verify Chrome: `chromium-browser --version`
- [ ] Verify ChromeDriver: `chromedriver --version`

---

## ☑️ Set Up Git (3 minutes)

```bash
ssh-keygen -t ed25519 -C "comiccaster-bot@yourdomain.com"
cat ~/.ssh/id_ed25519.pub
```

- [ ] Copy the SSH public key
- [ ] GitHub → Repo → Settings → Deploy keys → Add
- [ ] Paste key, title: "ComicCaster Droplet"
- [ ] ✅ Check "Allow write access"
- [ ] Configure git:
  ```bash
  git config --global user.name "ComicCaster Bot"
  git config --global user.email "comiccaster-bot@yourdomain.com"
  ```

---

## ☑️ Clone and Install (5 minutes)

```bash
cd /root
git clone git@github.com:adamprime/comiccaster.git
cd comiccaster
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

- [ ] Verify: `python -c "import selenium; print('OK')"`

---

## ☑️ Set Up Credentials (3 minutes)

```bash
vim ~/.comiccaster_env
```

Add (replace with real values):
```bash
export GOCOMICS_EMAIL="your-email@example.com"
export GOCOMICS_PASSWORD="your-password"
export COMICSKINGDOM_USERNAME="your-email@example.com"
export COMICSKINGDOM_PASSWORD="your-password"
export COMICSKINGDOM_COOKIE_FILE="/root/comiccaster/data/comicskingdom_cookies.pkl"
```

```bash
chmod 600 ~/.comiccaster_env
echo "source ~/.comiccaster_env" >> ~/.bashrc
source ~/.bashrc
```

- [ ] Verify: `echo $GOCOMICS_EMAIL` (should show your email)

---

## ☑️ Copy Cookies from Local (2 minutes)

**On your Mac:**
```bash
cd /Users/adam/coding/rss-comics
scp data/comicskingdom_cookies.pkl root@YOUR_DROPLET_IP:/root/comiccaster/data/
```

**On droplet:**
- [ ] Verify: `ls -lh /root/comiccaster/data/comicskingdom_cookies.pkl`

---

## ☑️ Test Setup (3 minutes)

```bash
cd /root/comiccaster
source venv/bin/activate
python scripts/test_droplet_setup.py
```

- [ ] All checks should pass ✅

---

## ☑️ Test Manual Run (5 minutes)

```bash
cd /root/comiccaster
source venv/bin/activate
source ~/.comiccaster_env
python scripts/droplet_daily_update.py
```

- [ ] GoComics scraping succeeds
- [ ] Comics Kingdom scraping succeeds
- [ ] Feeds generated
- [ ] Git push succeeds
- [ ] Check GitHub repo for new commit

---

## ☑️ Set Up Cron (2 minutes)

```bash
crontab -e
```

Add this line:
```bash
0 9 * * * /root/comiccaster/scripts/droplet_cron.sh >> /var/log/comiccaster.log 2>&1
```

- [ ] Save and exit
- [ ] Verify: `crontab -l`

---

## ☑️ Set Up Logging (1 minute)

```bash
touch /var/log/comiccaster.log
chmod 644 /var/log/comiccaster.log
```

- [ ] Test viewing logs: `tail /var/log/comiccaster.log`

---

## ☑️ Final Verification (Next Day)

Wait for cron to run (9 AM UTC), then:

```bash
tail -100 /var/log/comiccaster.log
```

- [ ] Cron ran at scheduled time
- [ ] All steps completed successfully
- [ ] New commit appeared in GitHub
- [ ] Feeds updated on comiccaster.xyz

---

## 🎉 You're Done!

**Total Setup Time:** ~35 minutes

**What Happens Now:**
- Every day at 9 AM UTC, the droplet automatically:
  1. Scrapes GoComics (~400 comics)
  2. Scrapes Comics Kingdom (~13 comics)
  3. Generates RSS feeds
  4. Pushes to GitHub
  5. Netlify auto-deploys

**Maintenance:** Just check logs once a week

---

## 📞 Need Help?

Review [DROPLET_SETUP.md](DROPLET_SETUP.md) for detailed troubleshooting steps.

Common issues:
- **Git push fails:** Check deploy key permissions
- **Chrome crashes:** Upgrade to $12/month droplet (2GB RAM)
- **Auth fails:** Re-copy cookies from local machine
