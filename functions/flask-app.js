const { spawn } = require('child_process');
const path = require('path');
const process = require('process');

// Set up proper Python environment
process.env.PYTHONPATH = process.cwd() + ':' + process.env.PYTHONPATH;

// Function to execute Flask app as a subprocess
exports.handler = async function(event, context) {
  // Configure Flask app through environment variables
  process.env.FLASK_ENV = 'production';
  process.env.SERVER_NAME = event.headers.host || 'comiccaster.xyz';
  
  // Parse the path - remove the function path prefix if present
  let requestPath = event.path;
  if (requestPath.startsWith('/.netlify/functions/flask-app')) {
    requestPath = requestPath.replace('/.netlify/functions/flask-app', '');
  }
  if (requestPath === '') {
    requestPath = '/';
  }
  
  console.log('Request path:', requestPath);
  
  // Prepare arguments for Flask subprocess
  const args = [
    '-m', 'flask',
    'routes',  // Just list routes for debugging
    '--no-debugger'
  ];

  return new Promise((resolve, reject) => {
    try {
      // Call the Flask app with the request details
      const flask = spawn('python', args, {
        env: process.env,
        cwd: process.cwd()
      });
      
      let stdout = '';
      let stderr = '';
      
      flask.stdout.on('data', (data) => {
        stdout += data.toString();
      });
      
      flask.stderr.on('data', (data) => {
        stderr += data.toString();
      });
      
      flask.on('close', (code) => {
        if (code !== 0) {
          console.error(`Flask process exited with code ${code}`);
          console.error('Stderr:', stderr);
          
          // Return a helpful error message
          resolve({
            statusCode: 500,
            headers: {
              'Content-Type': 'text/html',
            },
            body: `
              <html>
                <head>
                  <title>ComicCaster - Service Error</title>
                  <style>
                    body { font-family: system-ui, sans-serif; line-height: 1.5; padding: 2rem; background: #1a1a1a; color: #fff; }
                    .container { max-width: 800px; margin: 0 auto; }
                  </style>
                </head>
                <body>
                  <div class="container">
                    <h1>ComicCaster Service Error</h1>
                    <p>We're experiencing technical difficulties with our Flask application.</p>
                    <p>You can still access individual comic feeds directly:</p>
                    <ul>
                      <li><a href="/rss/calvinandhobbes" style="color: #3b82f6;">/rss/calvinandhobbes</a></li>
                      <li><a href="/rss/dilbert" style="color: #3b82f6;">/rss/dilbert</a></li>
                      <li><a href="/rss/garfield" style="color: #3b82f6;">/rss/garfield</a></li>
                    </ul>
                    <a href="/" style="display: inline-block; margin-top: 1rem; padding: 0.5rem 1rem; background: #0066cc; color: white; text-decoration: none; border-radius: 4px;">Try Again</a>
                    <div style="margin-top: 2rem; border-top: 1px solid #333; padding-top: 1rem;">
                      <p>Error details:</p>
                      <pre style="background: #333; padding: 1rem; overflow: auto; border-radius: 4px;">${stderr}</pre>
                    </div>
                  </div>
                </body>
              </html>
            `
          });
          return;
        }
        
        console.log('Flask routes:', stdout);
        
        // For now, return information about our Flask app
        resolve({
          statusCode: 200,
          headers: {
            'Content-Type': 'text/html',
          },
          body: `
            <html>
              <head>
                <title>ComicCaster - Redirecting</title>
                <meta http-equiv="refresh" content="0;url=/" />
                <style>
                  body { font-family: system-ui, sans-serif; line-height: 1.5; padding: 2rem; background: #1a1a1a; color: #fff; }
                  .container { max-width: 800px; margin: 0 auto; text-align: center; }
                </style>
              </head>
              <body>
                <div class="container">
                  <h1>ComicCaster</h1>
                  <p>Redirecting to main app...</p>
                  <p>If you are not redirected, <a href="/" style="color: #3b82f6;">click here</a>.</p>
                </div>
              </body>
            </html>
          `
        });
      });
    } catch (error) {
      console.error('Error running Flask:', error);
      resolve({
        statusCode: 500,
        body: `Server error: ${error.message}`
      });
    }
  });
}; 