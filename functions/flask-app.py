import os
import sys
import json
from flask import Flask, request

# Add project to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our Flask app
from comiccaster.web_interface import app as flask_app

def handler(event, context):
    """
    Netlify Function handler for the Flask app.
    """
    # Parse request details from Netlify event
    method = event['httpMethod']
    path = event['path']
    
    # Remove function prefix if present
    if path.startswith('/.netlify/functions/flask-app'):
        path = path.replace('/.netlify/functions/flask-app', '')
    
    # Ensure path starts with a slash
    if not path:
        path = '/'
    
    # Set environment variables
    os.environ['SERVER_NAME'] = event['headers'].get('host', 'comiccaster.xyz')
    
    # Prepare WSGI environment
    environ = {
        'REQUEST_METHOD': method,
        'PATH_INFO': path,
        'QUERY_STRING': '',
        'SERVER_NAME': os.environ['SERVER_NAME'],
        'SERVER_PORT': '443',
        'HTTP_HOST': os.environ['SERVER_NAME'],
        'wsgi.url_scheme': 'https',
        'wsgi.input': '',
        'wsgi.errors': sys.stderr,
    }
    
    # Handle query parameters
    if event.get('queryStringParameters'):
        query_string = '&'.join([f"{k}={v}" for k, v in event['queryStringParameters'].items()])
        environ['QUERY_STRING'] = query_string
    
    # Handle headers
    for header, value in event.get('headers', {}).items():
        key = header.upper().replace('-', '_')
        if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            key = 'HTTP_' + key
        environ[key] = value
    
    # Handle body
    if event.get('body'):
        environ['wsgi.input'] = event['body']
        environ['CONTENT_LENGTH'] = str(len(event['body']))
    
    # Capture the response
    response = {'statusCode': 200, 'headers': {}, 'body': ''}
    
    def start_response(status, response_headers, exc_info=None):
        status_code = int(status.split(' ')[0])
        response['statusCode'] = status_code
        
        for key, value in response_headers:
            response['headers'][key] = value
    
    # Call the Flask app
    output = flask_app(environ, start_response)
    response['body'] = ''.join([chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk for chunk in output])
    
    return response 