/**
 * Netlify Function: Mr. Boffo Image Proxy
 *
 * mrboffo.com is served over plain HTTP only (no TLS). Embedding its image
 * directly in a feed produces a mixed-content image that HTTPS browsers and
 * web-based RSS readers block, even though native readers load it fine. This
 * function fetches the image server-side and re-serves it over HTTPS from
 * comiccaster.xyz so it renders everywhere.
 *
 * Usage: /.netlify/functions/proxy-mrboffo-image?url=http://www.mrboffo.com/images/daily/...
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

    // Security: parse the URL and match the hostname EXACTLY. A substring
    // check (imageUrl.includes('mrboffo.com')) is an SSRF bypass — it would
    // accept http://mrboffo.com.evil.com/ or http://evil/?x=mrboffo.com.
    let parsed;
    try {
      parsed = new URL(imageUrl);
    } catch (e) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Invalid url parameter' })
      };
    }

    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return {
        statusCode: 403,
        body: JSON.stringify({ error: 'Disallowed URL scheme' })
      };
    }

    const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
    const allowedHosts = ['mrboffo.com', 'www.mrboffo.com'];
    if (!allowedHosts.includes(host)) {
      console.warn(`Rejected non-Mr. Boffo URL: ${imageUrl}`);
      return {
        statusCode: 403,
        body: JSON.stringify({ error: 'Only Mr. Boffo images are allowed' })
      };
    }

    // Fetch the image (mrboffo.com is HTTP-only and does not require a Referer).
    // redirect: 'manual' so a redirect can't bounce us off the allowed host.
    console.log(`Proxying image: ${parsed.toString()}`);

    const response = await fetch(parsed.toString(), {
      redirect: 'manual',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
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

    // Only ever serve images back — never let the proxy relay arbitrary
    // content types (would make it a general-purpose exfiltration endpoint).
    const contentType = response.headers.get('content-type') || 'image/jpeg';
    if (!contentType.toLowerCase().startsWith('image/')) {
      console.warn(`Refusing non-image content-type: ${contentType}`);
      return {
        statusCode: 415,
        body: JSON.stringify({ error: 'Upstream did not return an image' })
      };
    }

    // Get image data
    const imageBuffer = await response.arrayBuffer();

    console.log(`Successfully proxied image (${imageBuffer.byteLength} bytes, ${contentType})`);

    // Return the image
    return {
      statusCode: 200,
      headers: {
        'Content-Type': contentType,
        // Cache for 24 hours - the daily strip changes at most once per day
        'Cache-Control': 'public, max-age=86400, s-maxage=86400',
        // Allow CORS for RSS readers
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
        // Indicate this is a proxied resource
        'X-Proxy-Source': 'mrboffo.com'
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
