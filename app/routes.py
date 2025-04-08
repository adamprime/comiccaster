import os
from flask import render_template
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