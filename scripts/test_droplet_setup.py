#!/usr/bin/env python3
"""
Test script to verify droplet setup is correct.

Run this on the droplet after initial setup to verify
everything is configured properly.
"""

import os
import sys
from pathlib import Path
import subprocess

def check_command(cmd, description):
    """Check if a command is available."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"✅ {description}")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"❌ {description} - NOT FOUND")
        return False

def check_env_var(var_name):
    """Check if environment variable is set."""
    value = os.getenv(var_name)
    if value:
        print(f"✅ {var_name}: {'*' * min(len(value), 20)}")
        return True
    else:
        print(f"❌ {var_name}: NOT SET")
        return False

def check_file(file_path, description):
    """Check if a file exists."""
    path = Path(file_path)
    if path.exists():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: NOT FOUND")
        return False

def main():
    print("="*80)
    print("ComicCaster Droplet Setup Verification")
    print("="*80)
    print()
    
    all_checks = []
    
    # Check system commands
    print("📦 System Commands:")
    all_checks.append(check_command(['python3', '--version'], 'Python 3'))
    all_checks.append(check_command(['git', '--version'], 'Git'))
    all_checks.append(check_command(['chromium-browser', '--version'], 'Chrome'))
    all_checks.append(check_command(['chromedriver', '--version'], 'ChromeDriver'))
    print()
    
    # Check Python packages
    print("🐍 Python Packages:")
    try:
        import selenium
        print(f"✅ Selenium: {selenium.__version__}")
        all_checks.append(True)
    except ImportError:
        print("❌ Selenium: NOT INSTALLED")
        all_checks.append(False)
    
    try:
        from feedgen.feed import FeedGenerator
        print("✅ Feedgen: Installed")
        all_checks.append(True)
    except ImportError:
        print("❌ Feedgen: NOT INSTALLED")
        all_checks.append(False)
    
    try:
        import requests
        print("✅ Requests: Installed")
        all_checks.append(True)
    except ImportError:
        print("❌ Requests: NOT INSTALLED")
        all_checks.append(False)
    print()
    
    # Check environment variables
    print("🔐 Environment Variables:")
    all_checks.append(check_env_var('GOCOMICS_EMAIL'))
    all_checks.append(check_env_var('GOCOMICS_PASSWORD'))
    all_checks.append(check_env_var('COMICSKINGDOM_USERNAME'))
    all_checks.append(check_env_var('COMICSKINGDOM_PASSWORD'))
    all_checks.append(check_env_var('COMICSKINGDOM_COOKIE_FILE'))
    print()
    
    # Check files
    print("📁 Required Files:")
    all_checks.append(check_file('/root/comiccaster', 'Project directory'))
    all_checks.append(check_file('/root/comiccaster/authenticated_scraper_secure.py', 'GoComics scraper'))
    all_checks.append(check_file('/root/comiccaster/comicskingdom_scraper_secure.py', 'Comics Kingdom scraper'))
    all_checks.append(check_file('/root/comiccaster/scripts/droplet_daily_update.py', 'Daily update script'))
    all_checks.append(check_file('/root/comiccaster/scripts/droplet_cron.sh', 'Cron wrapper'))
    all_checks.append(check_file('/root/comiccaster/data/comicskingdom_cookies.pkl', 'Comics Kingdom cookies'))
    print()
    
    # Check Git configuration
    print("🔧 Git Configuration:")
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True,
            text=True,
            cwd='/root/comiccaster'
        )
        if result.stdout.strip():
            print(f"✅ Git user.name: {result.stdout.strip()}")
            all_checks.append(True)
        else:
            print("❌ Git user.name: NOT SET")
            all_checks.append(False)
    except Exception:
        print("❌ Git configuration: ERROR")
        all_checks.append(False)
    
    # Check SSH key
    if Path('/root/.ssh/id_ed25519').exists():
        print("✅ SSH key: Found")
        all_checks.append(True)
    else:
        print("❌ SSH key: NOT FOUND")
        all_checks.append(False)
    print()
    
    # Summary
    print("="*80)
    passed = sum(all_checks)
    total = len(all_checks)
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"Results: {passed}/{total} checks passed ({success_rate:.0f}%)")
    print("="*80)
    
    if all(all_checks):
        print("\n✅ All checks passed! Droplet is ready.")
        print("\nNext steps:")
        print("  1. Test manual run: python3 scripts/droplet_daily_update.py")
        print("  2. Set up cron: crontab -e")
        return 0
    else:
        print("\n❌ Some checks failed. Review the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
