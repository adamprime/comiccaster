// Netlify function to redirect to the main Flask app or provide information

exports.handler = async function(event, context) {
  // Get the server's base URL
  const host = event.headers.host || 'comiccaster.xyz';
  const protocol = event.headers.referer?.startsWith('https') ? 'https' : 'http';
  const baseUrl = `${protocol}://${host}`;
  
  // HTML response with information and redirects
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ComicCaster - RSS feeds for your favorite comics</title>
    <meta http-equiv="refresh" content="5;url=${baseUrl}" />
    <style>
        :root {
            --background-color: #1a1a1a;
            --text-color: #ffffff;
            --border-color: #333333;
        }

        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            line-height: 1.5;
            margin: 0;
            padding: 20px;
            background: var(--background-color);
            color: var(--text-color);
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
        }

        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }

        .card {
            background: var(--background-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 2rem;
            overflow: hidden;
            padding: 1.5rem;
            text-align: left;
        }

        .btn {
            display: inline-block;
            padding: 0.5rem 1rem;
            font-size: 1rem;
            font-weight: 500;
            text-align: center;
            text-decoration: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s;
            border: none;
            background-color: #0066cc;
            color: white;
            margin-top: 1rem;
        }

        a {
            color: #3b82f6;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>ComicCaster</h1>
        <p>Redirecting you to the homepage in 5 seconds...</p>
        
        <div class="card">
            <h2>Available RSS Features:</h2>
            <ul>
                <li>Individual feeds: <code>${baseUrl}/rss/[comic-slug]</code></li>
                <li>Example: <a href="${baseUrl}/rss/calvinandhobbes">${baseUrl}/rss/calvinandhobbes</a></li>
            </ul>
            <p>Visit the <a href="${baseUrl}">main site</a> to browse all available comics and create OPML files.</p>
            <a href="${baseUrl}" class="btn">Go to Homepage</a>
        </div>
    </div>
</body>
</html>
  `;
  
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'text/html',
    },
    body: html
  };
}; 