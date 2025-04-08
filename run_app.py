#!/usr/bin/env python3
"""
ComicCaster Web Application

This script runs the ComicCaster web application, which provides a web interface
for users to select their favorite comics and generate a personalized RSS feed.
"""

import os
from comiccaster.web_interface import app

if __name__ == '__main__':
    # Set the host and port from environment variables or use defaults
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5001))
    
    # Run the Flask application
    app.run(host=host, port=port, debug=True) 