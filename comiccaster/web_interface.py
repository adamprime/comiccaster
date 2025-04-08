"""
Web Interface Module for ComicCaster

This module provides a web interface for users to:
1. View available individual comic feeds
2. Select their favorite comics
3. Generate a personalized combined RSS feed
"""

import os
import json
import uuid
import re
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from datetime import datetime, timedelta
from functools import wraps

# Import our existing modules
from comiccaster.loader import ComicsLoader
from comiccaster.scraper import ComicScraper
from comiccaster.feed_generator import ComicFeedGenerator
from comiccaster.feed_aggregator import FeedAggregator

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-for-testing')

# Configure server name for URL generation
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME', 'comiccaster.xyz')
elif os.environ.get('FLASK_ENV') == 'development':
    app.config['SERVER_NAME'] = 'localhost:5000'

# In-memory storage for temporary feed tokens (in production, use a proper database)
# Format: {token: {'comics': [comic_slugs], 'created_at': timestamp}}
feed_tokens = {}

# Load the comics list
loader = ComicsLoader()

# Initialize the feed aggregator
feed_aggregator = FeedAggregator()

@app.route('/')
def index():
    """Render the home page with the comic selection interface."""
    comics_data = loader.get_comics_list()
    return render_template('index.html', comics=comics_data)

@app.route('/rss/<comic_slug>')
def individual_feed(comic_slug):
    """Serve an individual comic's RSS feed."""
    feed_path = f'feeds/{comic_slug}.xml'
    
    # Check if the feed exists
    if not os.path.exists(feed_path):
        return f"Feed for {comic_slug} not found", 404
    
    # Serve the XML file with the correct content type
    with open(feed_path, 'r') as f:
        return Response(f.read(), mimetype='application/xml')

@app.route('/feed/<token>')
def combined_feed(token):
    """Serve a combined RSS feed based on a token."""
    if token not in feed_tokens:
        error_msg = "Invalid or expired token"
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'error': error_msg}), 404
        return error_msg, 404
    
    token_data = feed_tokens[token]
    selected_comics = token_data['comics']
    
    # Generate the combined feed
    feed_xml = feed_aggregator.generate_feed(selected_comics)
    
    # Return the feed with the correct content type
    return Response(feed_xml, mimetype='application/rss+xml')

@app.route('/generate-feed', methods=['POST'])
def generate_feed():
    """Generate a combined feed URL based on selected comics (supports both form and JSON)."""
    # Handle JSON request
    if request.is_json:
        data = request.get_json()
        if not data or 'comics' not in data:
            return jsonify({'error': 'No comics selected'}), 400
        selected_comics = data['comics']
    # Handle form request
    else:
        selected_comics = request.form.getlist('comics')
        if not selected_comics:
            flash("Please select at least one comic")
            return redirect(url_for('index'))
    
    # Validate comics
    comics_list = loader.get_comics_list()
    valid_comics = [c for c in selected_comics if c in comics_list]
    if not valid_comics:
        if request.is_json:
            return jsonify({'error': 'No valid comics selected'}), 400
        flash("No valid comics selected")
        return redirect(url_for('index'))
    
    # Generate feed URL and token
    token, feed_url = create_feed_token(valid_comics)
    
    # Return appropriate response format
    if request.is_json:
        return jsonify({
            'token': token,
            'feed_url': feed_url
        })
    return render_template('feed_generated.html', feed_url=feed_url)

def create_feed_token(comics):
    """Create a token and feed URL for the given comics."""
    token = str(uuid.uuid4())
    
    # Store the selection with the token
    feed_tokens[token] = {
        'comics': comics,
        'created_at': datetime.now()
    }
    
    # Clean up old tokens (older than 30 days)
    cleanup_old_tokens()
    
    # Generate the feed URL
    feed_url = url_for('combined_feed', token=token, _external=True)
    
    return token, feed_url

def cleanup_old_tokens():
    """Remove tokens older than 30 days."""
    now = datetime.now()
    expired_tokens = [
        token for token, data in feed_tokens.items()
        if (now - data['created_at']) > timedelta(days=30)
    ]
    
    for token in expired_tokens:
        del feed_tokens[token]

if __name__ == '__main__':
    app.run(debug=True) 