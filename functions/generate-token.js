const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');

// Helper function to check if a comic feed exists
function comicFeedExists(slug) {
    const feedPath = path.join(process.cwd(), 'public', 'feeds', `${slug}.xml`);
    return fs.existsSync(feedPath);
}

// Helper function to store token data
function storeToken(token, comics) {
    const tokensPath = path.join(process.cwd(), 'public', 'data', 'tokens.json');
    let tokens = {};
    
    // Create data directory if it doesn't exist
    const dataDir = path.join(process.cwd(), 'public', 'data');
    if (!fs.existsSync(dataDir)) {
        fs.mkdirSync(dataDir, { recursive: true });
    }
    
    // Load existing tokens if file exists
    if (fs.existsSync(tokensPath)) {
        try {
            tokens = JSON.parse(fs.readFileSync(tokensPath, 'utf8'));
        } catch (error) {
            console.error('Error parsing tokens.json:', error);
            // Continue with empty tokens object
        }
    }
    
    // Store new token data
    tokens[token] = {
        comics,
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString() // 7 days
    };
    
    // Save updated tokens
    fs.writeFileSync(tokensPath, JSON.stringify(tokens, null, 2));
    return token;
}

exports.handler = async function(event, context) {
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            body: JSON.stringify({ error: 'Method Not Allowed' })
        };
    }

    try {
        let comics = [];
        try {
            const body = JSON.parse(event.body);
            comics = body.comics || [];
        } catch (error) {
            return {
                statusCode: 400,
                body: JSON.stringify({ error: 'Invalid request body' })
            };
        }
        
        if (!Array.isArray(comics) || comics.length === 0) {
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
        const token = uuidv4();
        storeToken(token, availableComics);

        // Generate OPML content
        const opml = generateOPML(availableComics);

        // Return response based on Accept header
        const acceptHeader = event.headers?.accept || '';
        if (acceptHeader.includes('application/json')) {
            // Return JSON response with token
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    token: token,
                    feed_url: `${process.env.URL}/feed/${token}`
                })
            };
        } else {
            // Return OPML as attachment
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/xml',
                    'Content-Disposition': 'attachment; filename="comiccaster-feeds.opml"'
                },
                body: opml
            };
        }
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
    const baseUrl = process.env.URL || 'https://comiccaster.xyz';
    
    const feeds = comics.map(slug => {
        // Format the comic name nicely
        const comicName = slug.replace(/-/g, ' ')
            .replace(/(^|\s)\S/g, l => l.toUpperCase());
            
        return `            <outline 
                type="rss" 
                text="${comicName}"
                title="${comicName}"
                xmlUrl="${baseUrl}/.netlify/functions/individual-feed?comic=${slug}"
            />`;
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