const fs = require('fs');
const path = require('path');

// Helper function to check if a comic feed exists
function comicFeedExists(slug) {
    const feedPath = path.join(process.cwd(), 'public', 'feeds', `${slug}.xml`);
    return fs.existsSync(feedPath);
}

// Helper function to load comics list
function loadComicsList() {
    try {
        const comicsPath = path.join(process.cwd(), 'public', 'comics_list.json');
        if (fs.existsSync(comicsPath)) {
            return JSON.parse(fs.readFileSync(comicsPath, 'utf8'));
        }
    } catch (error) {
        console.error('Error loading comics list:', error);
    }
    return [];
}

// Generate OPML content
function generateOPML(comics) {
    const date = new Date().toISOString();
    const baseUrl = process.env.URL || 'https://comiccaster.xyz';
    const comicsList = loadComicsList();
    
    // Create a mapping of slugs to comic names
    const slugToName = {};
    comicsList.forEach(comic => {
        slugToName[comic.slug] = comic.name;
    });
    
    const feeds = comics.map(slug => {
        // Use the comic name from comics_list.json if available, otherwise format the slug
        let comicName = slugToName[slug];
        if (!comicName) {
            comicName = slug.replace(/-/g, ' ').replace(/(^|\s)\S/g, l => l.toUpperCase());
        }
            
        return `            <outline 
                type="rss" 
                text="${comicName}"
                title="${comicName}"
                xmlUrl="${baseUrl}/rss/${slug}"
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

        // Generate OPML content without token creation
        const opml = generateOPML(availableComics);

        // Return OPML as attachment
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