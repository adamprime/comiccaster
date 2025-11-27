#!/usr/bin/env python3
"""
Daily update script for ComicCaster droplet.

This script handles the complete daily update workflow:
1. Scrape GoComics
2. Scrape Comics Kingdom
3. Generate all RSS feeds
4. Commit and push to GitHub
5. Netlify auto-deploys from GitHub push

Designed to run via cron once per day.
"""

import os
import sys
import subprocess
import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_command(cmd, description, cwd=None):
    """Run a command and handle errors."""
    print(f"\n{'='*80}")
    print(f"▶️  {description}")
    print(f"{'='*80}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per command
        )
        
        if result.stdout:
            print(result.stdout)
        
        print(f"✅ {description} - SUCCESS")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"❌ {description} - TIMEOUT (10 minutes)")
        return False
        
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False
        
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False


def main():
    """Run the daily update workflow."""
    start_time = datetime.datetime.now()
    print("\n" + "="*80)
    print(f"🚀 ComicCaster Daily Update")
    print(f"📅 {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("="*80)
    
    results = {
        'gocomics': False,
        'comicskingdom': False,
        'feeds': False,
        'git_push': False
    }
    
    # Ensure we're in the right directory
    os.chdir(PROJECT_ROOT)
    
    # Activate virtual environment (if it exists)
    venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python3'
    python_cmd = str(venv_python) if venv_python.exists() else 'python3'
    
    # Step 1: Scrape GoComics
    results['gocomics'] = run_command(
        [python_cmd, 'authenticated_scraper_secure.py', '--output-dir', './data'],
        "Scraping GoComics (400+ comics)"
    )
    
    # Step 2: Scrape Comics Kingdom
    results['comicskingdom'] = run_command(
        [python_cmd, 'comicskingdom_scraper_secure.py', '--output-dir', './data'],
        "Scraping Comics Kingdom"
    )
    
    # Step 3: Generate all RSS feeds
    # GoComics feeds
    gocomics_feeds = run_command(
        [python_cmd, 'scripts/update_feeds.py'],
        "Generating GoComics RSS feeds"
    )
    
    # Comics Kingdom feeds (only if scraping succeeded)
    ck_feeds = True
    if results['comicskingdom']:
        ck_feeds = run_command(
            [python_cmd, 'scripts/generate_comicskingdom_feeds.py'],
            "Generating Comics Kingdom RSS feeds"
        )
    else:
        print("\n⚠️  Skipping Comics Kingdom feeds (scraping failed)")
    
    results['feeds'] = gocomics_feeds and ck_feeds
    
    # Step 4: Commit and push to GitHub
    print(f"\n{'='*80}")
    print("▶️  Committing and pushing to GitHub")
    print(f"{'='*80}")
    
    # Check if there are changes
    git_status = subprocess.run(
        ['git', 'status', '--porcelain'],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    
    if git_status.stdout.strip():
        # Add files
        run_command(
            ['git', 'add', 'public/feeds/*.xml', 'data/*.json'],
            "Staging changes"
        )
        
        # Commit
        commit_msg = f"Update comic feeds - {datetime.datetime.now().strftime('%Y-%m-%d')}"
        results['git_push'] = run_command(
            ['git', 'commit', '-m', commit_msg],
            "Creating commit"
        )
        
        # Push
        if results['git_push']:
            results['git_push'] = run_command(
                ['git', 'push'],
                "Pushing to GitHub"
            )
    else:
        print("ℹ️  No changes to commit")
        results['git_push'] = True  # Not a failure
    
    # Summary
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"GoComics Scraping:       {'✅ SUCCESS' if results['gocomics'] else '❌ FAILED'}")
    print(f"Comics Kingdom Scraping: {'✅ SUCCESS' if results['comicskingdom'] else '❌ FAILED'}")
    print(f"Feed Generation:         {'✅ SUCCESS' if results['feeds'] else '❌ FAILED'}")
    print(f"Git Push:                {'✅ SUCCESS' if results['git_push'] else '❌ FAILED'}")
    print(f"\n⏱️  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"🕐 Completed: {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("="*80)
    
    # Exit code
    if all(results.values()):
        print("\n✅ Daily update completed successfully!")
        return 0
    else:
        print("\n⚠️  Daily update completed with some failures")
        return 1


if __name__ == '__main__':
    sys.exit(main())
