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
    const queryParams = new URLSearchParams(event.queryStringParameters || {});
    slug = queryParams.get('comic') || event.path.split('/').pop();
  }
  
  console.log('Requested comic slug:', slug);
  
  if (!slug) {
    return {
      statusCode: 400,
      body: 'Comic slug is required'
    };
  }
  
  try {
    // Try to read the feed file from the feeds directory
    const feedPath = path.join(process.cwd(), 'feeds', `${slug}.xml`);
    
    // If not found in feeds directory, check public/feeds as fallback
    if (!fs.existsSync(feedPath)) {
      const publicFeedPath = path.join(process.cwd(), 'public', 'feeds', `${slug}.xml`);
      
      if (!fs.existsSync(publicFeedPath)) {
        return {
          statusCode: 404,
          body: `Feed for ${slug} not found`
        };
      }
      
      const feedContent = fs.readFileSync(publicFeedPath, 'utf8');
      
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/xml',
          'Cache-Control': 'public, max-age=3600' // Cache for 1 hour
        },
        body: feedContent
      };
    }
    
    const feedContent = fs.readFileSync(feedPath, 'utf8');
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/xml',
        'Cache-Control': 'public, max-age=3600' // Cache for 1 hour
      },
      body: feedContent
    };
  } catch (error) {
    console.error(`Error serving feed for ${slug}:`, error);
    return {
      statusCode: 500,
      body: `Error serving feed: ${error.message}`
    };
  }
}; 