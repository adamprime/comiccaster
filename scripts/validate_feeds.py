#!/usr/bin/env python3
"""
Validate that comic feeds are updating properly.
Uses a set of known daily comics as "canaries" to detect update issues.
"""

import os
import sys
import feedparser
from datetime import datetime, timedelta
import logging
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Canary comics - a mix of popular and reliable daily updaters
CANARY_COMICS = [
    # Popular, well-known comics
    'garfield',
    'pearlsbeforeswine', 
    'doonesbury',
    'calvinandhobbes',
    'peanuts',
    'babyblues',
    'adamathome',
    'brewsterrockit',
    
    # Additional reliable daily comics
    'baldo',
    'brevity',
    'freerange',
    'lacucaracha',
    'overboard',
    'pickles',
    'speedbump'
]

def check_feed_freshness(feed_path, max_age_days=3):
    """
    Check if a feed has recent entries.
    
    Args:
        feed_path: Path to the feed XML file
        max_age_days: Maximum age in days for the most recent entry
        
    Returns:
        dict: Status information about the feed
    """
    try:
        feed = feedparser.parse(feed_path)
        
        if not feed.entries:
            return {
                'status': 'ERROR',
                'message': 'No entries in feed',
                'latest_date': None
            }
        
        # Get the most recent entry
        latest_entry = feed.entries[0]
        
        # Extract publication date
        if hasattr(latest_entry, 'published_parsed') and latest_entry.published_parsed:
            pub_date = datetime(*latest_entry.published_parsed[:6])
        else:
            return {
                'status': 'ERROR',
                'message': 'No publication date found',
                'latest_date': None
            }
        
        # Calculate age
        age = datetime.now() - pub_date
        age_days = age.days
        
        # Extract date from title as backup verification
        title_date = None
        if ' - ' in latest_entry.title:
            date_part = latest_entry.title.split(' - ')[-1]
            try:
                title_date = datetime.strptime(date_part, '%Y-%m-%d')
            except:
                pass
        
        # Determine status
        if age_days <= max_age_days:
            status = 'OK'
            message = f'Latest entry is {age_days} days old'
        else:
            status = 'STALE'
            message = f'Latest entry is {age_days} days old (exceeds {max_age_days} day threshold)'
        
        return {
            'status': status,
            'message': message,
            'latest_date': pub_date.strftime('%Y-%m-%d'),
            'age_days': age_days,
            'title': latest_entry.title
        }
        
    except Exception as e:
        return {
            'status': 'ERROR',
            'message': f'Failed to parse feed: {str(e)}',
            'latest_date': None
        }

def validate_canary_feeds():
    """Validate all canary comic feeds."""
    feeds_dir = os.path.join(os.path.dirname(__file__), '..', 'public', 'feeds')
    
    results = {
        'check_time': datetime.now().isoformat(),
        'canaries': {},
        'summary': {
            'total': len(CANARY_COMICS),
            'ok': 0,
            'stale': 0,
            'error': 0
        }
    }
    
    logger.info(f"Validating {len(CANARY_COMICS)} canary comic feeds...")
    
    for comic_slug in CANARY_COMICS:
        feed_path = os.path.join(feeds_dir, f'{comic_slug}.xml')
        
        if not os.path.exists(feed_path):
            result = {
                'status': 'ERROR',
                'message': 'Feed file not found',
                'latest_date': None
            }
        else:
            result = check_feed_freshness(feed_path)
        
        results['canaries'][comic_slug] = result
        results['summary'][result['status'].lower()] += 1
        
        # Log individual results
        if result['status'] == 'OK':
            logger.info(f"✅ {comic_slug}: {result['message']}")
        elif result['status'] == 'STALE':
            logger.warning(f"⚠️  {comic_slug}: {result['message']}")
        else:
            logger.error(f"❌ {comic_slug}: {result['message']}")
    
    return results

def main():
    """Main validation function."""
    results = validate_canary_feeds()
    
    # Print summary
    print("\n" + "=" * 60)
    print("FEED VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total canary comics: {results['summary']['total']}")
    print(f"✅ OK: {results['summary']['ok']}")
    print(f"⚠️  Stale: {results['summary']['stale']}")
    print(f"❌ Error: {results['summary']['error']}")
    
    # Save results to file
    output_path = os.path.join(os.path.dirname(__file__), '..', 'feed_validation_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_path}")
    
    # Exit with error code if any feeds are stale or errored
    if results['summary']['stale'] > 0 or results['summary']['error'] > 0:
        print("\n⚠️  VALIDATION FAILED: Some feeds are not updating properly!")
        
        # In GitHub Actions, this could trigger an issue creation
        if os.environ.get('GITHUB_ACTIONS'):
            print("\nCreating GitHub issue for feed update problems...")
            # This would be handled by the workflow
        
        return 1
    else:
        print("\n✅ All canary feeds are updating properly!")
        return 0

if __name__ == "__main__":
    sys.exit(main())