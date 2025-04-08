import pytest
from flask import url_for
from comiccaster.web_interface import app
import json
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_comics_list():
    """Mock the comics list."""
    return ['test-comic']

@pytest.fixture
def mock_feed_entries():
    """Mock feed entries for test comic."""
    return [{
        'title': 'Test Comic',
        'link': 'http://example.com/test',
        'description': 'Test description',
        'published': datetime.now().isoformat()
    }]

@pytest.fixture
def mock_loader(monkeypatch, mock_comics_list, mock_feed_entries):
    """Mock the loader functionality."""
    mock = MagicMock()
    mock.get_comics_list.return_value = mock_comics_list
    mock.load_feed_entries.return_value = mock_feed_entries
    monkeypatch.setattr('comiccaster.web_interface.loader', mock)
    return mock

def test_index_page(client, mock_loader):
    """Test that the index page loads successfully."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'ComicCaster' in response.data

def test_combined_feed_generation(client, mock_loader):
    """Test generating a combined feed."""
    response = client.post('/generate-feed', json={
        'comics': ['test-comic']
    })
    assert response.status_code == 200
    data = response.get_json()
    assert 'token' in data
    assert 'feed_url' in data
    assert data['feed_url'].endswith('/feed/' + data['token'])

def test_combined_feed_invalid_comics(client, mock_loader):
    """Test generating a combined feed with invalid comics."""
    mock_loader.get_comics_list.return_value = []  # No valid comics
    response = client.post('/generate-feed', json={
        'comics': ['invalid-comic']
    })
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
    assert data['error'] == 'No valid comics selected'

@pytest.mark.network
def test_feed_access(client, mock_loader):
    """Test accessing a generated feed."""
    # First generate a feed
    response = client.post('/generate-feed', json={
        'comics': ['test-comic']
    })
    assert response.status_code == 200
    data = response.get_json()
    token = data['token']

    # Then access the feed
    response = client.get(f'/feed/{token}')
    assert response.status_code == 200
    assert response.mimetype == 'application/rss+xml'

def test_invalid_token(client, mock_loader):
    """Test accessing feed with invalid token."""
    response = client.get('/feed/invalid-token')
    assert response.status_code == 404

def test_token_expiry(client, mock_loader):
    """Test that expired tokens are rejected."""
    # TODO: Implement token expiry test
    pass 