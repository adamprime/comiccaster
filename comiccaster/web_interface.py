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
from comiccaster.feed_generator import FeedGenerator
from comiccaster.feed_aggregator import FeedAggregator

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-for-testing')

# In-memory storage for temporary feed tokens (in production, use a proper database)
# Format: {token: {'comics': [comic_slugs], 'created_at': timestamp}}
feed_tokens = {}

# Load the comics list
loader = ComicsLoader()
comics_data = loader.load_comics_from_file('comics_list.json')

# Initialize the feed aggregator
feed_aggregator = FeedAggregator()

@app.route('/')
def index():
    """Render the home page with the comic selection interface."""
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

@app.route('/combined', methods=['GET'])
def combined_feed():
    """Generate and serve a combined RSS feed based on selected comics."""
    # Get the comics from the query parameter or token
    comics_param = request.args.get('comics')
    token = request.args.get('token')
    
    if not comics_param and not token:
        return "No comics selected", 400
    
    selected_comics = []
    
    if token:
        # Retrieve selection from token
        if token not in feed_tokens:
            return "Invalid or expired token", 404
        
        token_data = feed_tokens[token]
        selected_comics = token_data['comics']
    else:
        # Parse the comics from the query parameter
        selected_comics = comics_param.split(',')
    
    # Validate that all requested comics exist
    valid_comics = [c for c in selected_comics if c in comics_data]
    
    if not valid_comics:
        return "No valid comics selected", 400
    
    # Generate the combined feed
    feed_xml = feed_aggregator.aggregate_feeds(valid_comics)
    
    # Return the feed with the correct content type
    return Response(feed_xml, mimetype='application/xml')

@app.route('/generate', methods=['POST'])
def generate_feed():
    """Generate a combined feed URL based on selected comics."""
    selected_comics = request.form.getlist('comics')
    
    if not selected_comics:
        flash("Please select at least one comic")
        return redirect(url_for('index'))
    
    # Generate a unique token
    token = str(uuid.uuid4())
    
    # Store the selection with the token
    feed_tokens[token] = {
        'comics': selected_comics,
        'created_at': datetime.now()
    }
    
    # Clean up old tokens (older than 30 days)
    cleanup_old_tokens()
    
    # Generate the feed URL
    feed_url = url_for('combined_feed', token=token, _external=True)
    
    return render_template('feed_generated.html', feed_url=feed_url)

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