const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');

// Helper function to check if a comic feed exists
function comicFeedExists(slug) {
    const feedPath = path.join(process.cwd(), 'feeds', `${slug}.xml`);
    return fs.existsSync(feedPath);
}

// Helper function to store token data
function storeToken(token, comics) {
    const tokensPath = path.join(process.cwd(), 'data', 'tokens.json');
    let tokens = {};
    
    // Create data directory if it doesn't exist
    const dataDir = path.join(process.cwd(), 'data');
    if (!fs.existsSync(dataDir)) {
        fs.mkdirSync(dataDir);
    }
    
    // Load existing tokens if file exists
    if (fs.existsSync(tokensPath)) {
        tokens = JSON.parse(fs.readFileSync(tokensPath, 'utf8'));
    }
    
    // Store new token data
    tokens[token] = {
        comics,
        createdAt: new Date().toISOString()
    };
    
    // Save updated tokens
    fs.writeFileSync(tokensPath, JSON.stringify(tokens, null, 2));
    return token;
}

exports.handler = async function(event, context) {
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            body: 'Method Not Allowed'
        };
    }

    try {
        const { comics } = JSON.parse(event.body);
        
        if (!comics || !Array.isArray(comics) || comics.length === 0) {
            return {
                statusCode: 400,
                body: JSON.stringify({ error: 'Please select at least one comic' })
            };
        }

        // Filter out comics without feeds
        const availableComics = comics.filter(comicFeedExists);

        if (availableComics.length === 0) {
            return {
                statusCode: 400,
                body: JSON.stringify({ error: 'None of the selected comics have available feeds' })
            };
        }

        // Generate a unique token and store it
        const token = storeToken(uuidv4(), availableComics);

        // Generate OPML content
        const opml = generateOPML(availableComics);

        // Set cookie with the token
        const cookieExpiration = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/xml',
                'Content-Disposition': 'attachment; filename="comiccaster-feeds.opml"',
                'Set-Cookie': `comiccaster_token=${token}; Expires=${cookieExpiration.toUTCString()}; Path=/; HttpOnly; SameSite=Strict`
            },
            body: opml
        };
    } catch (error) {
        console.error('Error generating OPML:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Failed to generate OPML file' })
        };
    }
};

function generateOPML(comics) {
    const date = new Date().toISOString();
    const feeds = comics.map(slug => {
        return `    <outline 
            type="rss" 
            text="${slug.replace(/-/g, ' ').replace(/(^|\s)\S/g, l => l.toUpperCase())}"
            title="${slug.replace(/-/g, ' ').replace(/(^|\s)\S/g, l => l.toUpperCase())}"
            xmlUrl="${process.env.URL}/.netlify/functions/individual-feed?comic=${slug}"
        />`
    }).join('\n');

    return `<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>ComicCaster Feeds</title>
        <dateCreated>${date}</dateCreated>
    </head>
    <body>
        <outline text="Comics" title="Comics">
${feeds}
        </outline>
    </body>
</opml>`;
} 