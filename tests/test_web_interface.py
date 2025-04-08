import pytest
from flask import url_for
from comiccaster.web_interface import app
import json
import os

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    """Test that the index page loads successfully."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'ComicCaster' in response.data

def test_combined_feed_generation(client):
    """Test combined feed generation with valid comics."""
    test_comics = ['calvinandhobbes', 'peanuts']
    response = client.post('/generate-feed', json={'comics': test_comics})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'feed_url' in data
    assert 'token' in data

def test_combined_feed_invalid_comics(client):
    """Test combined feed generation with invalid comics."""
    test_comics = ['nonexistentcomic1', 'nonexistentcomic2']
    response = client.post('/generate-feed', json={'comics': test_comics})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

@pytest.mark.network
def test_feed_access(client):
    """Test accessing a generated feed."""
    # First generate a feed
    test_comics = ['calvinandhobbes']
    response = client.post('/generate-feed', json={'comics': test_comics})
    data = json.loads(response.data)
    token = data['token']
    
    # Then try to access it
    response = client.get(f'/combined-feed?token={token}')
    assert response.status_code == 200
    assert 'application/rss+xml' in response.headers['Content-Type']

def test_invalid_token(client):
    """Test accessing feed with invalid token."""
    response = client.get('/combined-feed?token=invalid-token')
    assert response.status_code == 404

def test_token_expiry(client):
    """Test that expired tokens are rejected."""
    # TODO: Implement token expiry test
    pass 