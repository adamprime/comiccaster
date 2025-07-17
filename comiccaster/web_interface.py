"""
Web Interface Module for ComicCaster

This module provides a web interface for users to:
1. View available individual comic feeds
2. Select their favorite comics
3. Generate an OPML file for importing feeds into RSS readers
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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-for-testing')

# Configure server name for URL generation
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME', 'comiccaster.xyz')
elif os.environ.get('FLASK_ENV') == 'development':
    app.config['SERVER_NAME'] = 'localhost:5001'  # Updated to match our current port

# Load the comics list
loader = ComicsLoader()

# Store for generated tokens and selected comics
tokens = {}

@app.route('/')
def index():
    """Render the home page with the comic selection interface."""
    comics_data = loader.load_comics_from_file()
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
def access_feed(token):
    """Access a previously generated feed by token (for backwards compatibility)."""
    if token not in tokens:
        return "Feed not found", 404
        
    feed_data = tokens[token]
    
    # Check if token is expired
    if datetime.now() > feed_data['expires']:
        del tokens[token]
        return "Feed has expired", 410
    
    # Generate a simple RSS feed for the selected comics
    feed_xml = "<?xml version='1.0' encoding='UTF-8'?>\n"
    feed_xml += "<rss version='2.0'>\n"
    feed_xml += "  <channel>\n"
    feed_xml += "    <title>ComicCaster Custom Feed</title>\n"
    feed_xml += "    <description>A custom comic feed</description>\n"
    feed_xml += "    <link>https://comiccaster.xyz</link>\n"
    
    for comic in feed_data['comics']:
        feed_xml += f"    <item>\n"
        feed_xml += f"      <title>{comic}</title>\n"
        feed_xml += f"      <link>https://gocomics.com/{comic}</link>\n"
        feed_xml += f"    </item>\n"
    
    feed_xml += "  </channel>\n"
    feed_xml += "</rss>"
    
    return Response(feed_xml, mimetype='application/rss+xml')

def generate_opml(comics_data, selected_slugs):
    """Generate OPML content for the selected comics."""
    date = datetime.now().isoformat()
    
    # Start with the OPML header
    opml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>ComicCaster Feeds</title>
        <dateCreated>{date}</dateCreated>
    </head>
    <body>
        <outline text="Comics" title="Comics">
"""
    
    # Add each selected comic as an outline
    for comic in comics_data:
        if comic['slug'] in selected_slugs:
            feed_url = url_for('individual_feed', comic_slug=comic['slug'], _external=True)
            opml += f"""            <outline 
                type="rss" 
                text="{comic['name']}"
                title="{comic['name']}"
                xmlUrl="{feed_url}"
            />\n"""
    
    # Close the OPML structure
    opml += """        </outline>
    </body>
</opml>"""
    
    return opml

@app.route('/generate-feed', methods=['POST'])
def generate_feed():
    """Generate an OPML file for the selected comics or return token for combined feed."""
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
    valid_slugs = [comic['slug'] for comic in loader.load_comics_from_file()]
    valid_comics = [slug for slug in selected_comics if slug in valid_slugs]
    
    if not valid_comics:
        if request.is_json:
            return jsonify({'error': 'No valid comics selected'}), 400
        flash("No valid comics selected")
        return redirect(url_for('index'))
    
    # For JSON requests (API/testing), return token-based response
    if request.is_json:
        # Generate a token for API/test access
        token = str(uuid.uuid4())
        tokens[token] = {
            'comics': valid_comics,
            'expires': datetime.now() + timedelta(days=7)
        }
        feed_url = url_for('access_feed', token=token, _external=True)
        return jsonify({'token': token, 'feed_url': feed_url})
    
    # For form submissions (browser), need comics data with metadata for OPML
    comics_data = loader.load_comics_from_file()
    comics_with_metadata = [comic for comic in comics_data if comic['slug'] in valid_comics]
    
    # Generate OPML content
    opml_content = generate_opml(comics_with_metadata, valid_comics)
    
    # Return the OPML file
    response = Response(opml_content, mimetype='application/xml')
    response.headers['Content-Disposition'] = 'attachment; filename=comiccaster-feeds.opml'
    return response

@app.route('/generate-opml', methods=['POST'])
def generate_opml_file():
    """Generate an OPML file for selected comics directly (no token generation)."""
    try:
        # Get selected comics from form
        selected_comics = request.form.getlist('comics')
        
        if not selected_comics:
            flash("Please select at least one comic")
            return redirect(url_for('index'))
        
        # Validate comics
        valid_slugs = [comic['slug'] for comic in loader.load_comics_from_file()]
        valid_comics = [slug for slug in selected_comics if slug in valid_slugs]
        
        if not valid_comics:
            flash("No valid comics selected")
            return redirect(url_for('index'))
        
        # For form submissions (browser), need comics data with metadata for OPML
        comics_data = loader.load_comics_from_file()
        comics_with_metadata = [comic for comic in comics_data if comic['slug'] in valid_comics]
        
        # Generate OPML content
        opml_content = generate_opml(comics_with_metadata, valid_comics)
        
        # Return the OPML file
        response = Response(opml_content, mimetype='application/xml')
        response.headers['Content-Disposition'] = 'attachment; filename=comiccaster-feeds.opml'
        return response
    
    except Exception as e:
        app.logger.error(f"Error generating OPML: {str(e)}")
        flash("Error generating OPML file")
        return redirect(url_for('index'))

if __name__ == '__main__':
    # Only enable debug mode if explicitly set in environment
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    app.run(debug=debug) 