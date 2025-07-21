from scripts.update_feeds import scrape_comic, regenerate_feed
from datetime import datetime, timedelta
import pytz

# Test comic info
comic = {
    'name': 'Calvin and Hobbes',
    'slug': 'calvinandhobbes',
    'url': 'https://www.gocomics.com/calvinandhobbes',
    'author': 'Bill Watterson'
}

# Get last 5 days of comics
TIMEZONE = pytz.timezone('US/Eastern')
today = datetime.now(TIMEZONE)
entries = []

# Test dates (last 5 days)
test_dates = [(today - timedelta(days=i)).strftime('%Y/%m/%d') for i in range(4, -1, -1)]

print('Testing comic scraping for last 5 days...')
for date in test_dates:
    print(f'\nTesting date: {date}')
    result = scrape_comic(comic, date)
    if result:
        print(f'Successfully scraped image: {result["image_url"]}')
        entries.append({
            'id': f'calvinandhobbes_{date.replace("/", "-")}',
            'title': f'Calvin and Hobbes - {date}',
            'url': f'https://www.gocomics.com/calvinandhobbes/{date}',
            'image_url': result['image_url'],
            'description': f'Calvin and Hobbes for {date}',
            'pub_date': datetime.strptime(date, '%Y/%m/%d')
        })

print(f'\nTotal entries found: {len(entries)}')
if entries:
    success = regenerate_feed(comic, entries)
    print(f'Feed regeneration {"successful" if success else "failed"}') 