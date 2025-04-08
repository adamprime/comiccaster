const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');

// Helper function to check if a comic feed exists
function comicFeedExists(slug) {
    const feedPath = path.join(process.cwd(), 'feeds', `${slug}.xml`);
    return fs.existsSync(feedPath);
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

        // Generate OPML content
        const opml = generateOPML(availableComics);

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/xml',
                'Content-Disposition': 'attachment; filename="comiccaster-feeds.opml"'
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