const Parser = require('rss-parser');
const parser = new Parser();

exports.handler = async function(event, context) {
    // Only allow POST requests
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }

    try {
        const { url } = JSON.parse(event.body);
        
        if (!url) {
            return {
                statusCode: 400,
                body: JSON.stringify({ error: 'No URL provided' })
            };
        }

        // Handle local development URLs
        let feedUrl = url;
        if (url.includes('comiccaster.xyz') && process.env.CONTEXT === 'dev') {
            // In local development, replace production URL with localhost
            feedUrl = url.replace('https://comiccaster.xyz', 'http://localhost:8888');
            console.log('Rewriting URL for local development:', feedUrl);
        }

        // Parse the feed
        const feed = await parser.parseURL(feedUrl);
        
        // Transform the feed data
        const transformedFeed = {
            title: feed.title,
            description: feed.description,
            link: feed.link,
            items: feed.items.map(item => ({
                title: item.title,
                description: item.content || item.description,
                link: item.link,
                pubDate: item.pubDate || item.isoDate,
                enclosures: item.enclosures || []
            }))
        };

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'public, max-age=300' // Cache for 5 minutes
            },
            body: JSON.stringify(transformedFeed)
        };
    } catch (error) {
        console.error('Error fetching feed:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Failed to fetch or parse feed' })
        };
    }
}; 