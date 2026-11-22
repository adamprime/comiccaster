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
    // Check all catalog lists, including external direct RSS feeds
    const dailyComicsList = loadComicsList('daily');
    const politicalComicsList = loadComicsList('political');
    const spanishComicsList = loadComicsList('spanish');
    const tinyviewComicsList = loadComicsList('tinyview');
    const externalComicsList = loadComicsList('external');
    
    if ((dailyComicsList && dailyComicsList.some(comic => comic.slug === slug)) ||
        (politicalComicsList && politicalComicsList.some(comic => comic.slug === slug)) ||
        (spanishComicsList && spanishComicsList.some(comic => comic.slug === slug)) ||
        (tinyviewComicsList && tinyviewComicsList.some(comic => comic.slug === slug)) ||
        (externalComicsList && externalComicsList.some(comic => comic.slug === slug))) {
        console.log(`Comic ${slug} found in comics list`);
        return true;
    }

    console.log(`No feed found for: ${slug}`);
    return false;
}

// Helper function to load comics list
function loadComicsList(type = 'daily') {
    try {
        // Try to use require() first - this should work with Netlify's bundler
        try {
            if (type === 'political') {
                const politicalComics = require('./political_comics_list.json');
                console.log(`Loaded ${politicalComics.length} political comics using require()`);
                return politicalComics;
            } else if (type === 'spanish') {
                const spanishComics = require('./spanish_comics_list.json');
                console.log(`Loaded ${spanishComics.length} spanish comics using require()`);
                return spanishComics;
            } else if (type === 'tinyview') {
                const tinyviewComics = require('./tinyview_comics_list.json');
                console.log(`Loaded ${tinyviewComics.length} tinyview comics using require()`);
                return tinyviewComics;
            } else if (type === 'external') {
                const externalComics = require('./external_comics_list.json');
                console.log(`Loaded ${externalComics.length} external comics using require()`);
                return externalComics;
            } else {
                const dailyComics = require('./comics_list.json');
                console.log(`Loaded ${dailyComics.length} daily comics using require()`);
                return dailyComics;
            }
        } catch (requireError) {
            console.log('Could not load using require(), trying fs methods:', requireError.message);
        }
        
        const functionDir = path.dirname(__filename);
        console.log('Function directory:', functionDir);
        
        // Determine the filename based on type
        const filename = type === 'political' ? 'political_comics_list.json' : 
                         type === 'spanish' ? 'spanish_comics_list.json' :
                         type === 'tinyview' ? 'tinyview_comics_list.json' : 
                         type === 'external' ? 'external_comics_list.json' :
                         'comics_list.json';
        
        // List contents of function directory
        console.log('Contents of function directory:');
        try {
            const files = fs.readdirSync(functionDir);
            console.log(files);
        } catch (error) {
            console.log('Error reading function directory:', error);
        }
        
        // Try to read from function directory first
        const functionPath = path.join(functionDir, filename);
        console.log('Function path:', functionPath);
        
        try {
            if (fs.existsSync(functionPath)) {
                console.log(`Found ${type} comics list in function directory`);
                const data = JSON.parse(fs.readFileSync(functionPath, 'utf8'));
                console.log(`Loaded ${data.length} ${type} comics from list`);
                return data;
            }
        } catch (error) {
            console.log('Error reading function path:', error);
        }
        
        // Fallback paths if function path fails
        const fallbackPaths = [
            path.join(functionDir, 'data', filename),
            path.join(functionDir, '..', 'public', filename),
            path.join('public', filename),
            path.join(filename)
        ];

        console.log('Trying fallback paths:', fallbackPaths);

        for (const comicsPath of fallbackPaths) {
            console.log(`Checking fallback path: ${comicsPath}`);
            try {
                if (fs.existsSync(comicsPath)) {
                    console.log(`Found ${type} comics list at fallback path: ${comicsPath}`);
                    const data = JSON.parse(fs.readFileSync(comicsPath, 'utf8'));
                    console.log(`Loaded ${data.length} ${type} comics from list`);
                    return data;
                }
            } catch (error) {
                console.log(`Error checking/reading ${comicsPath}:`, error);
            }
        }
    } catch (error) {
        console.error(`Error loading ${type} comics list:`, error);
    }
    console.log(`No ${type} comics list found in any location`);
    return [];
}

// Comic names go into XML attributes; seven daily names contain '&'.
function escapeXml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Generate OPML content
function generateOPML(comics, type = 'daily') {
    const date = new Date().toISOString();
    const baseUrl = process.env.URL || 'https://comiccaster.xyz';
    const comicsList = loadComicsList(type);
    
    // Create a mapping of slugs to comic names
    const slugToName = {};
    comicsList.forEach(comic => {
        slugToName[comic.slug] = comic.name;
    });
    
    // Create a mapping of slugs to comic data (name and source)
    const slugToComic = {};
    comicsList.forEach(comic => {
        slugToComic[comic.slug] = comic;
    });
    
    const feeds = comics.map(slug => {
        // Use the comic data from comics_list.json if available
        const comic = slugToComic[slug];
        let comicName = comic ? comic.name : slug.replace(/-/g, ' ').replace(/(^|\s)\S/g, l => l.toUpperCase());
        
        // Determine feed URL based on source
        // GoComics uses /rss/{slug}, others use /feeds/{slug}.xml
        let feedUrl;
        if (comic && comic.source === 'external-rss' && comic.feed_url) {
            feedUrl = comic.feed_url;
        } else if (comic && (comic.source === 'comicskingdom' || comic.source === 'tinyview' ||
                      comic.source === 'farside' || comic.source === 'newyorker' ||
                      comic.source === 'creators' || comic.source === 'mrboffo')) {
            feedUrl = `${baseUrl}/feeds/${slug}.xml`;
        } else {
            feedUrl = `${baseUrl}/rss/${slug}`;
        }
            
        comicName = escapeXml(comicName);
        return `            <outline
                type="rss"
                text="${comicName}"
                title="${comicName}"
                xmlUrl="${escapeXml(feedUrl)}"
            />`;
    }).join('\n');

    const categoryTitle = type === 'political' ? 'Political Cartoons' : 
                         type === 'spanish' ? 'Spanish Comics' :
                         type === 'tinyview' ? 'TinyView Comics' : 
                         type === 'external' ? 'External RSS Comics' :
                         'Comics';
    const opmlTitle = type === 'political' ? 'ComicCaster Political Cartoons' : 
                     type === 'spanish' ? 'ComicCaster Spanish Comics' :
                     type === 'tinyview' ? 'ComicCaster TinyView Comics' : 
                     type === 'external' ? 'ComicCaster External RSS Comics' :
                     'ComicCaster Daily Comics';

    return `<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>${opmlTitle}</title>
        <dateCreated>${date}</dateCreated>
    </head>
    <body>
        <outline text="${categoryTitle}" title="${categoryTitle}">
${feeds}
        </outline>
    </body>
</opml>`;
}

function opmlFilename(type) {
    const filename = type === 'political' ? 'political-cartoons.opml' :
                    type === 'spanish' ? 'spanish-comics.opml' :
                    type === 'tinyview' ? 'tinyview-comics.opml' :
                    type === 'external' ? 'external-comics.opml' :
                    'daily-comics.opml';
    return filename;
}

// Return OPML as attachment
function opmlResponse(opml, type, extraHeaders = {}) {
    return {
        statusCode: 200,
        headers: {
            'Content-Type': 'application/xml',
            'Content-Disposition': `attachment; filename="${opmlFilename(type)}"`,
            ...extraHeaders
        },
        body: opml
    };
}

// GET form: a plain link returns the same OPML as the POST form, so an agent
// can hand a person a link and a person can share one:
//   /.netlify/functions/generate-opml?type=daily&comics=peanuts,pickles
// It only looks slugs up in the comic lists and never fetches anything.
//
// One category per link. Slugs aren't unique across the lists (false-knees is
// ComicCaster's feed under daily and the publisher's feed under external), so
// the category decides which feed a slug means, as it does for the POST form.
const LINK_TYPES = ['daily', 'political', 'spanish', 'tinyview', 'external'];
const MAX_LINK_COMICS = 100;
// Fits 100 of the longest slugs with the commas percent-encoded.
const MAX_LINK_QUERY_LENGTH = 5000;

function linkError(statusCode, error, extra = {}) {
    return {
        statusCode,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error, ...extra })
    };
}

function siteUrl() {
    return process.env.URL || 'https://comiccaster.xyz';
}

function linkExample() {
    return `${siteUrl()}/.netlify/functions/generate-opml?type=daily&comics=peanuts,pickles`;
}

// Netlify passes repeated parameters in multiValueQueryStringParameters and
// joins them with ', ' in queryStringParameters (checked under netlify dev).
function queryValues(event, key) {
    const multi = event.multiValueQueryStringParameters;
    if (multi && multi[key] !== undefined) return [].concat(multi[key]);
    const single = event.queryStringParameters && event.queryStringParameters[key];
    return single === undefined || single === null ? [] : [single];
}

function queryLength(event) {
    if (typeof event.rawQuery === 'string') return event.rawQuery.length;
    const params = event.multiValueQueryStringParameters || event.queryStringParameters || {};
    return Object.entries(params)
        .reduce((length, [key, values]) => length + key.length + 2 + [].concat(values).join('&').length, 0);
}

function handleLink(event) {
    if (queryLength(event) > MAX_LINK_QUERY_LENGTH) {
        return linkError(414, `The query is longer than ${MAX_LINK_QUERY_LENGTH} characters`);
    }

    const types = queryValues(event, 'type');
    const type = types.length === 0 ? 'daily' : types[0];
    if (types.length > 1 || !LINK_TYPES.includes(type)) {
        return linkError(400,
            `type must be one of ${LINK_TYPES.join(', ')}, one per link ` +
            '(Far Side and New Yorker comics are in daily)',
            { example: linkExample() });
    }

    const requested = [...new Set(queryValues(event, 'comics')
        .flatMap(value => value.split(','))
        .map(slug => slug.trim())
        .filter(Boolean))];
    if (requested.length === 0) {
        return linkError(400, 'Please select at least one comic', { example: linkExample() });
    }
    if (requested.length > MAX_LINK_COMICS) {
        return linkError(400, `A link can bundle at most ${MAX_LINK_COMICS} comics`);
    }

    const comicsList = loadComicsList(type);
    if (comicsList.length === 0) {
        console.error(`No ${type} comics list found - this is a critical error`);
        return linkError(500, `${type} comics list not found - please contact support`);
    }

    // The POST form's filter (comicFeedExists) also passes a slug from another
    // list, or any path naming a feed file, which then gets a made-up name or a
    // URL that 404s. A link keeps only the slugs listed in its own category.
    const listed = new Set(comicsList.map(comic => comic.slug));
    const availableComics = requested.filter(slug => listed.has(slug));
    if (availableComics.length === 0) {
        return linkError(400, 'None of the selected comics have available feeds', {
            details: `Use slugs from the ${type} category of ${siteUrl()}/catalog.json`
        });
    }

    return opmlResponse(generateOPML(availableComics, type), type,
        { 'Access-Control-Allow-Origin': '*' });
}

exports.handler = async function(event, context) {
    if (event.httpMethod === 'GET') {
        try {
            return handleLink(event);
        } catch (error) {
            console.error('Error generating OPML:', error);
            return linkError(500, 'Failed to generate OPML file');
        }
    }

    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            headers: { 'Allow': 'GET, POST' },
            body: JSON.stringify({ error: 'Method Not Allowed' })
        };
    }

    try {
        let comics = [];
        let type = 'daily';
        try {
            const body = JSON.parse(event.body);
            comics = body.comics || [];
            type = body.type || 'daily';
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
        const comicsList = loadComicsList(type);
        if (comicsList.length === 0) {
            console.error(`No ${type} comics list found - this is a critical error`);
            return {
                statusCode: 500,
                body: JSON.stringify({ error: `${type} comics list not found - please contact support` })
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
        const opml = generateOPML(availableComics, type);

        return opmlResponse(opml, type);
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
