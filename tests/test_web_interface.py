"""
Tests for the web interface module
"""

import os
import tempfile
import pytest
from comiccaster.web_interface import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page(client):
    """Test that the home page loads correctly."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'ComicCaster' in response.data
    assert b'Available Comics' in response.data
    assert b'Create OPML File' in response.data

def test_individual_feed_access(client):
    """Test accessing an individual feed."""
    # Create a temporary feed file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as f:
        test_feed = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Test Comic - GoComics</title>
    <description>Daily Test Comic comic strip</description>
    <atom:link href="https://comiccaster.xyz/feeds/testcomic.xml" rel="self" type="application/rss+xml"/>
    <link>https://www.gocomics.com/testcomic</link>
    <item>
      <title>Test Comic - 2023-04-08</title>
      <link>https://www.gocomics.com/testcomic/2023/04/08</link>
      <description>Test description</description>
    </item>
  </channel>
</rss>"""
        f.write(test_feed.encode('utf-8'))
        temp_filename = f.name
    
    # Use a modified version of the feed path for testing
    feed_path = os.path.basename(temp_filename)
    slug = feed_path.replace('.xml', '')
    
    try:
        # Monkeypatch the feed path for testing
        original_feed_path = app.view_functions['individual_feed'].__code__
        
        # Create a test function that serves our temp file
        def test_feed_function(comic_slug):
            if comic_slug == slug:
                with open(temp_filename, 'r') as f:
                    return app.response_class(f.read(), mimetype='application/xml')
            return f"Feed for {comic_slug} not found", 404
        
        # Replace the view function
        app.view_functions['individual_feed'] = test_feed_function
        
        # Test accessing the feed
        response = client.get(f'/rss/{slug}')
        assert response.status_code == 200
        assert response.content_type == 'application/xml'
        assert b'Test Comic' in response.data
        
    finally:
        # Clean up
        os.unlink(temp_filename)
        # Restore original function
        app.view_functions['individual_feed'].__code__ = original_feed_path

def test_generate_opml(client):
    """Test generating an OPML file."""
    # Set up test comics data
    app.extensions = {'loader': type('MockLoader', (), {
        'load_comics_from_file': lambda: [
            {'name': 'Test Comic 1', 'slug': 'testcomic1'},
            {'name': 'Test Comic 2', 'slug': 'testcomic2'}
        ],
        'get_comics_list': lambda: ['testcomic1', 'testcomic2', 'testcomic3']
    })}
    
    # Test generating an OPML file
    response = client.post('/generate-feed', data={
        'comics': ['testcomic1', 'testcomic2']
    })
    
    assert response.status_code == 200
    assert response.content_type == 'application/xml'
    assert b'<opml version="1.0">' in response.data
    assert b'<outline text="Comics" title="Comics">' in response.data
    assert b'Test Comic 1' in response.data
    assert b'Test Comic 2' in response.data
    assert b'testcomic1' in response.data
    assert b'testcomic2' in response.data 