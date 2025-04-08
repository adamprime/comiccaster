import os
import json
from datetime import datetime
from flask import render_template, jsonify, request, Response, url_for, redirect
from app import app
from scripts.update_feeds import load_comics_list

def get_available_comics():
    """Get list of comics that have available feeds."""
    comics = load_comics_list()
    return [comic for comic in comics if os.path.exists(f"feeds/{comic['slug']}.xml")]

@app.route('/')
def index():
    """Display the list of available comics."""
    comics = get_available_comics()
    return render_template('index.html', comics=comics)

@app.route('/api/available-comics')
def available_comics():
    """API endpoint for available comics."""
    comics = get_available_comics()
    return jsonify(comics)

@app.route('/generate-opml', methods=['POST'])
def generate_opml():
    """Generate an OPML file for selected comics."""
    try:
        # Get selected comics from form
        selected_comics = request.form.getlist('comics')
        
        if not selected_comics:
            return "No comics selected", 400
        
        all_comics = {comic['slug']: comic for comic in get_available_comics()}
        
        # Build OPML content
        opml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>ComicCaster Feeds</title>
        <dateCreated>{datetime.now().isoformat()}</dateCreated>
    </head>
    <body>
        <outline text="Comics" title="Comics">
'''
        
        for slug in selected_comics:
            if slug in all_comics:
                comic = all_comics[slug]
                feed_url = f"{request.url_root}feeds/{slug}.xml"
                opml_content += f'''            <outline 
                type="rss" 
                text="{comic['name']}"
                title="{comic['name']}"
                xmlUrl="{feed_url}"
            />
'''
        
        opml_content += '''        </outline>
    </body>
</opml>'''
        
        # Create response with OPML file
        response = Response(opml_content, mimetype='application/xml')
        response.headers['Content-Disposition'] = 'attachment; filename=comiccaster-feeds.opml'
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating OPML: {str(e)}")
        return "Error generating OPML file", 500

@app.route('/generate-feed', methods=['POST'])
def generate_feed():
    """Redirect to generate-opml route for form submissions."""
    if request.form:
        comics = request.form.getlist('comics')
        return redirect(url_for('generate_opml'), code=307)  # 307 preserves the POST method
    return "Invalid request", 400 