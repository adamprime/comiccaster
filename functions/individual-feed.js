const fs = require('fs');
const path = require('path');

exports.handler = async function(event, context) {
  // Get comic slug from path or query parameters
  let slug;
  
  // Check if we're being called via the /rss/ redirect
  if (event.path.startsWith('/rss/')) {
    slug = event.path.replace('/rss/', '');
  } else {
    // Otherwise check query parameters or the last part of the path
    const queryParams = event.queryStringParameters || {};
    slug = queryParams.comic || event.path.split('/').pop();
  }
  
  console.log('Requested comic slug:', slug);
  console.log('Event path:', event.path);
  console.log('Event query params:', JSON.stringify(event.queryStringParameters));
  
  if (!slug || slug === 'rss' || slug === '') {
    return {
      statusCode: 400,
      headers: {
        'Content-Type': 'text/html',
      },
      body: `
        <html>
          <head>
            <title>ComicCaster - Feed Error</title>
            <style>
              body { font-family: system-ui, sans-serif; line-height: 1.5; padding: 2rem; background: #1a1a1a; color: #fff; }
              .container { max-width: 800px; margin: 0 auto; }
              a { color: #3b82f6; }
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Comic Feed Error</h1>
              <p>No comic specified. Please use a URL in the format: <code>/rss/comic-name</code></p>
              <p>Example: <a href="/rss/calvinandhobbes">/rss/calvinandhobbes</a></p>
              <a href="/" style="display: inline-block; margin-top: 1rem; padding: 0.5rem 1rem; background: #0066cc; color: white; text-decoration: none; border-radius: 4px;">Go to Homepage</a>
            </div>
          </body>
        </html>
      `
    };
  }
  
  try {
    // Clean the slug to prevent directory traversal
    slug = slug.replace(/[^a-zA-Z0-9-_]/g, '');
    
    // First try the public/feeds directory (Netlify build output)
    let feedPath = path.join('public', 'feeds', `${slug}.xml`);
    
    // Check for file existence
    if (fs.existsSync(feedPath)) {
      console.log(`Serving feed from ${feedPath}`);
      const feedContent = fs.readFileSync(feedPath, 'utf8');
      
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/xml',
          'Cache-Control': 'public, max-age=3600' // Cache for 1 hour
        },
        body: feedContent
      };
    }
    
    // If not in public/feeds, try the feeds directory
    feedPath = path.join('feeds', `${slug}.xml`);
    
    if (fs.existsSync(feedPath)) {
      console.log(`Serving feed from ${feedPath}`);
      const feedContent = fs.readFileSync(feedPath, 'utf8');
      
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/xml',
          'Cache-Control': 'public, max-age=3600' // Cache for 1 hour
        },
        body: feedContent
      };
    }
    
    // Debug: List available feeds
    const publicFeedsDir = path.join('public', 'feeds');
    const feedsDir = path.join('feeds');
    
    let availableFeeds = [];
    
    try {
      if (fs.existsSync(publicFeedsDir)) {
        availableFeeds = availableFeeds.concat(fs.readdirSync(publicFeedsDir));
      }
    } catch (error) {
      console.error(`Error reading public/feeds directory:`, error);
    }
    
    try {
      if (fs.existsSync(feedsDir)) {
        availableFeeds = availableFeeds.concat(fs.readdirSync(feedsDir));
      }
    } catch (error) {
      console.error(`Error reading feeds directory:`, error);
    }
    
    // Remove duplicates
    availableFeeds = [...new Set(availableFeeds)];
    
    console.log(`Available feeds (${availableFeeds.length}):`, availableFeeds.slice(0, 10));
    
    // Feed not found
    return {
      statusCode: 404,
      headers: {
        'Content-Type': 'text/html',
      },
      body: `
        <html>
          <head>
            <title>ComicCaster - Feed Not Found</title>
            <style>
              body { font-family: system-ui, sans-serif; line-height: 1.5; padding: 2rem; background: #1a1a1a; color: #fff; }
              .container { max-width: 800px; margin: 0 auto; }
              a { color: #3b82f6; }
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Feed Not Found</h1>
              <p>The requested comic feed "${slug}" was not found.</p>
              <p>Here are some available feeds:</p>
              <ul>
                ${availableFeeds.slice(0, 10).map(feed => {
                  const feedSlug = feed.replace('.xml', '');
                  return `<li><a href="/rss/${feedSlug}">${feedSlug}</a></li>`;
                }).join('')}
              </ul>
              <a href="/" style="display: inline-block; margin-top: 1rem; padding: 0.5rem 1rem; background: #0066cc; color: white; text-decoration: none; border-radius: 4px;">Go to Homepage</a>
            </div>
          </body>
        </html>
      `
    };
  } catch (error) {
    console.error(`Error serving feed for ${slug}:`, error);
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'text/html',
      },
      body: `
        <html>
          <head>
            <title>ComicCaster - Feed Error</title>
            <style>
              body { font-family: system-ui, sans-serif; line-height: 1.5; padding: 2rem; background: #1a1a1a; color: #fff; }
              .container { max-width: 800px; margin: 0 auto; }
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Feed Error</h1>
              <p>There was an error serving the feed for "${slug}":</p>
              <pre style="background: #333; padding: 1rem; border-radius: 4px;">${error.message}</pre>
              <a href="/" style="display: inline-block; margin-top: 1rem; padding: 0.5rem 1rem; background: #0066cc; color: white; text-decoration: none; border-radius: 4px;">Go to Homepage</a>
            </div>
          </body>
        </html>
      `
    };
  }
}; 