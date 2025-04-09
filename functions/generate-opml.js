const fs = require('fs');
const path = require('path');

// Helper function to check if a comic feed exists
function comicFeedExists(slug) {
    // In production, files are in the function's data directory
    const functionDir = path.dirname(__filename);
    const dataDir = path.join(functionDir, 'data');
    
    // Try multiple possible locations for the feed files
    const possiblePaths = [
        path.join(dataDir, 'feeds', `${slug}.xml`),
        path.join(dataDir, `${slug}.xml`),
        path.join('public', 'feeds', `${slug}.xml`),
        path.join('feeds', `${slug}.xml`),
        // Add test environment paths
        path.join('test_functions', 'data', 'feeds', `${slug}.xml`),
        path.join('test_functions', 'data', `${slug}.xml`)
    ];

    console.log(`Checking feed existence for slug: ${slug}`);
    console.log('Function directory:', functionDir);
    console.log('Data directory:', dataDir);
    console.log('Checking paths:', possiblePaths);

    // Check each possible path
    for (const feedPath of possiblePaths) {
        console.log(`Checking path: ${feedPath}`);
        try {
            if (fs.existsSync(feedPath)) {
                console.log(`Found feed at: ${feedPath}`);
                return true;
            }
        } catch (error) {
            console.log(`Error checking path ${feedPath}:`, error);
        }
    }

    // If we have a comics list, consider that as validation too
    const comicsList = loadComicsList();
    if (comicsList && comicsList.some(comic => comic.slug === slug)) {
        console.log(`Comic ${slug} found in comics_list.json`);
        return true;
    }

    console.log(`No feed found for: ${slug}`);
    return false;
}

// Helper function to load comics list
function loadComicsList() {
    try {
        const functionDir = path.dirname(__filename);
        console.log('Function directory:', functionDir);
        
        // List contents of function directory
        console.log('Contents of function directory:');
        try {
            const files = fs.readdirSync(functionDir);
            console.log(files);
        } catch (error) {
            console.log('Error reading function directory:', error);
        }
        
        // Try to read from public directory first
        const publicPath = path.join(functionDir, '..', 'public', 'comics_list.json');
        console.log('Public path:', publicPath);
        
        try {
            if (fs.existsSync(publicPath)) {
                console.log('Found comics list in public directory');
                const data = JSON.parse(fs.readFileSync(publicPath, 'utf8'));
                console.log(`Loaded ${data.length} comics from list`);
                return data;
            }
        } catch (error) {
            console.log('Error reading public path:', error);
        }
        
        // Fallback paths if public path fails
        const fallbackPaths = [
            path.join(functionDir, 'data', 'comics_list.json'),
            path.join(functionDir, '..', 'functions', 'data', 'comics_list.json'),
            path.join('comics_list.json')
        ];

        console.log('Trying fallback paths:', fallbackPaths);

        for (const comicsPath of fallbackPaths) {
            console.log(`Checking fallback path: ${comicsPath}`);
            try {
                if (fs.existsSync(comicsPath)) {
                    console.log(`Found comics list at fallback path: ${comicsPath}`);
                    const data = JSON.parse(fs.readFileSync(comicsPath, 'utf8'));
                    console.log(`Loaded ${data.length} comics from list`);
                    return data;
                }
            } catch (error) {
                console.log(`Error checking/reading ${comicsPath}:`, error);
            }
        }
    } catch (error) {
        console.error('Error loading comics list:', error);
    }
    console.log('No comics list found in any location');
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

        // Load comics list first to validate slugs
        const comicsList = loadComicsList();
        if (comicsList.length === 0) {
            console.error('No comics list found - this is a critical error');
            return {
                statusCode: 500,
                body: JSON.stringify({ error: 'Comics list not found - please contact support' })
            };
        }

        // Filter out comics without feeds
        const availableComics = comics.filter(comicFeedExists);

        if (availableComics.length === 0) {
            return {
                statusCode: 400,
                body: JSON.stringify({ 
                    error: 'None of the selected comics have available feeds',
                    details: 'Please try again later or contact support if the issue persists'
                })
            };
        }

        // Generate OPML content
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
            body: JSON.stringify({ 
                error: 'Failed to generate OPML file',
                details: error.message
            })
        };
    }
}; 