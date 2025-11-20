/**
 * Netlify Function: Far Side Image Proxy
 * 
 * Proxies images from The Far Side website to bypass anti-hotlinking protection.
 * The Far Side images require a proper Referer header to load, which RSS readers
 * don't provide. This function fetches the image with the correct header and
 * returns it to the RSS reader.
 * 
 * Usage: /.netlify/functions/proxy-farside-image?url=https://siteassets.thefarside.com/...
 */

exports.handler = async (event, context) => {
  // Only allow GET requests
  if (event.httpMethod !== 'GET') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method not allowed' })
    };
  }

  try {
    const imageUrl = event.queryStringParameters?.url;
    
    if (!imageUrl) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Missing url parameter' })
      };
    }

    // Security: Only allow Far Side image URLs
    const allowedDomains = [
      'thefarside.com',
      'siteassets.thefarside.com'
    ];
    
    const isAllowed = allowedDomains.some(domain => imageUrl.includes(domain));
    
    if (!isAllowed) {
      console.warn(`Rejected non-Far Side URL: ${imageUrl}`);
      return {
        statusCode: 403,
        body: JSON.stringify({ error: 'Only Far Side images are allowed' })
      };
    }

    // Fetch the image with proper headers
    console.log(`Proxying image: ${imageUrl}`);
    
    const response = await fetch(imageUrl, {
      headers: {
        'Referer': 'https://www.thefarside.com/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      }
    });

    if (!response.ok) {
      console.error(`Failed to fetch image: ${response.status} ${response.statusText}`);
      return {
        statusCode: response.status,
        body: JSON.stringify({ 
          error: `Failed to fetch image: ${response.status} ${response.statusText}` 
        })
      };
    }

    // Get image data
    const imageBuffer = await response.arrayBuffer();
    const contentType = response.headers.get('content-type') || 'image/jpeg';

    console.log(`Successfully proxied image (${imageBuffer.byteLength} bytes, ${contentType})`);

    // Return the image
    return {
      statusCode: 200,
      headers: {
        'Content-Type': contentType,
        // Cache for 24 hours - comics don't change
        'Cache-Control': 'public, max-age=86400, s-maxage=86400',
        // Allow CORS for RSS readers
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
        // Indicate this is a proxied resource
        'X-Proxy-Source': 'thefarside.com'
      },
      body: Buffer.from(imageBuffer).toString('base64'),
      isBase64Encoded: true
    };

  } catch (error) {
    console.error('Error proxying image:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ 
        error: 'Internal server error',
        message: error.message 
      })
    };
  }
};
