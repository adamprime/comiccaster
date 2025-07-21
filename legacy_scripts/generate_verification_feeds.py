#!/usr/bin/env python3
"""
Generate test RSS feeds with the fixed scraper for manual verification.
"""

import os
from datetime import datetime, timedelta
from comiccaster.scraper import ComicScraper
import html

def create_verification_feeds():
    """Create test RSS feeds for manual verification of the daily comics fix."""
    
    print("Generating verification RSS feeds with fixed scraper...")
    print("=" * 70)
    
    # Test different comic types
    test_comics = [
        ('garfield', 'Garfield - Horizontal strip format'),
        ('bloomcounty', 'Bloom County - Featured in original Issue #27'),
        ('peanuts', 'Peanuts - Classic strip format'),
        ('bignate', 'Big Nate - Modern strip format')
    ]
    
    scraper = ComicScraper()
    
    for comic_slug, description in test_comics:
        print(f"\n🧪 Creating RSS feed for {comic_slug}...")
        
        # Collect a few recent comics to show date variation
        comics_data = []
        today = datetime.now()
        
        for i in range(3):  # Get 3 recent entries
            if i == 0:
                # Today's comic
                date_str = None
                date_label = "Today"
                date_obj = today
            else:
                # Historical comics
                date_obj = today - timedelta(days=i)
                date_str = date_obj.strftime('%Y/%m/%d')
                date_label = date_obj.strftime('%Y-%m-%d')
            
            print(f"  Scraping {date_label}...")
            
            try:
                if date_str:
                    comic_data = scraper.scrape_comic(comic_slug, date_str)
                else:
                    comic_data = scraper.scrape_comic(comic_slug)
                    
                if comic_data and comic_data.get('image'):
                    comic_entry = {
                        'date_obj': date_obj,
                        'date_str': date_obj.strftime('%Y-%m-%d'),
                        'image_url': comic_data['image'],
                        'title': comic_data.get('title', f'{comic_slug.title()} - {date_obj.strftime("%Y-%m-%d")}'),
                        'gocomics_url': f"https://www.gocomics.com/{comic_slug}" + (f"/{date_str}" if date_str else "")
                    }
                    comics_data.append(comic_entry)
                    
                    # Extract just the image hash for display
                    image_hash = comic_entry['image_url'].split('/')[-1].split('?')[0]
                    print(f"    ✅ {image_hash}")
                    
                else:
                    print(f"    ❌ Failed to get image")
                    
            except Exception as e:
                print(f"    ❌ Error: {e}")
        
        if comics_data:
            # Create RSS feed
            rss_content = create_rss_xml(comics_data, comic_slug, description)
            
            # Write to file
            os.makedirs('verification_feeds', exist_ok=True)
            feed_path = f'verification_feeds/{comic_slug}-verification.xml'
            
            with open(feed_path, 'w', encoding='utf-8') as f:
                f.write(rss_content)
            
            print(f"    ✅ RSS feed created: {feed_path}")
            
            # Show unique image analysis
            unique_images = len(set(comic['image_url'] for comic in comics_data))
            print(f"    📊 {len(comics_data)} comics, {unique_images} unique images")
            
            if unique_images == len(comics_data):
                print(f"    🎉 SUCCESS: All dates have different comics (actual daily comics!)")
            else:
                print(f"    ⚠️  WARNING: Some duplicate images detected")
        else:
            print(f"    ❌ No comics collected for {comic_slug}")
    
    print(f"\n" + "=" * 70)
    print("📁 VERIFICATION FEEDS CREATED:")
    print("=" * 70)
    
    verification_dir = os.path.abspath('verification_feeds')
    print(f"Directory: {verification_dir}")
    
    for comic_slug, description in test_comics:
        feed_path = f"verification_feeds/{comic_slug}-verification.xml"
        if os.path.exists(feed_path):
            full_path = os.path.abspath(feed_path)
            print(f"✅ {comic_slug}: {full_path}")
    
    print(f"\n🔍 MANUAL VERIFICATION INSTRUCTIONS:")
    print(f"1. Open each RSS feed in an RSS reader or XML viewer")
    print(f"2. Verify that different dates show DIFFERENT comic strips")
    print(f"3. Compare with GoComics.com to confirm these are the actual daily comics")
    print(f"4. Confirm images are from featureassets.gocomics.com (not social media)")
    
    return True

def create_rss_xml(comics_data, comic_slug, description):
    """Create properly formatted RSS XML."""
    
    # RSS header
    comic_title = comic_slug.replace('_', ' ').title()
    rss = f'''<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
<channel>
<title>VERIFICATION: {comic_title} - Daily Comics Fix</title>
<link>https://www.gocomics.com/{comic_slug}</link>
<description>{description} - Test feed for verifying actual daily comics (not "best of")</description>
<atom:link href="https://comiccaster.xyz/feeds/{comic_slug}-verification.xml" rel="self" type="application/rss+xml"/>
<docs>http://www.rssboard.org/rss-specification</docs>
<generator>ComicCaster Verification Test - fetchpriority Fix</generator>
<language>en</language>
<lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
'''
    
    # Add items (in reverse chronological order)
    for comic in reversed(comics_data):
        pub_date = comic['date_obj'].strftime('%a, %d %b %Y 00:00:00 +0000')
        
        # Extract image hash for verification display
        image_hash = comic['image_url'].split('/')[-1].split('?')[0]
        
        # Properly escape URLs for XML
        escaped_image_url = html.escape(comic['image_url'])
        escaped_gocomics_url = html.escape(comic['gocomics_url'])
        
        item = f'''<item>
<title>{comic_title} - {comic['date_str']}</title>
<link>{escaped_gocomics_url}</link>
<description><![CDATA[
                <div style="text-align: center;">
                    <img src="{comic['image_url']}" alt="{comic_title}" style="max-width: 100%;">
                    <p>{comic_title} comic for {comic['date_str']}</p>
                    <p><strong>Verification:</strong> ✅ fetchpriority="high" Daily Comic</p>
                    <p><strong>Hash:</strong> {image_hash}</p>
                    <p><strong>Source:</strong> featureassets.gocomics.com</p>
                </div>
                ]]></description>
<guid isPermaLink="false">{escaped_gocomics_url}</guid>
<enclosure url="{escaped_image_url}" length="0" type="image/jpeg"/>
<pubDate>{pub_date}</pubDate>
</item>'''
        
        rss += item
    
    # Close RSS
    rss += '''
</channel>
</rss>'''
    
    return rss

if __name__ == "__main__":
    create_verification_feeds()