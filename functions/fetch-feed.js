const fs = require('fs');
const path = require('path');
const Parser = require('rss-parser');
const parser = new Parser();

// The preview page (public/preview.html) is the only caller, and it only ever
// previews our own feeds or a listed external feed. Anything else is refused:
// this function used to fetch any URL it was sent, which made it an open proxy.
const OWN_HOSTS = ['comiccaster.xyz', 'www.comiccaster.xyz', 'comiccaster.netlify.app'];
// Deploy previews and branch deploys: <deploy>--comiccaster.netlify.app
const OWN_DEPLOY_HOST_SUFFIX = '--comiccaster.netlify.app';
const DEV_HOSTS = ['localhost', '127.0.0.1'];
const FEED_PATH = /^\/feeds\/[A-Za-z0-9_-]+\.xml$/;

function loadExternalFeedUrls() {
    let comics = null;
    try {
        // Copied next to the function by the Netlify build command.
        comics = require('./external_comics_list.json');
    } catch (requireError) {
        const candidates = [
            path.join(__dirname, 'external_comics_list.json'),
            path.join(__dirname, '..', 'public', 'external_comics_list.json'),
            path.join('public', 'external_comics_list.json'),
        ];
        const found = candidates.find((candidate) => fs.existsSync(candidate));
        if (found) {
            comics = JSON.parse(fs.readFileSync(found, 'utf8'));
        }
    }
    return new Set((comics || []).map((comic) => comic.feed_url).filter(Boolean));
}

const externalFeedUrls = loadExternalFeedUrls();

function isOwnFeed(parsed, isDev) {
    if (parsed.username || parsed.password || (parsed.port && !isDev)) {
        return false;
    }
    if (!FEED_PATH.test(parsed.pathname) || parsed.search) {
        return false;
    }
    const host = parsed.hostname.toLowerCase();
    if (isDev && parsed.protocol === 'http:' && DEV_HOSTS.includes(host)) {
        return true;
    }
    return parsed.protocol === 'https:' &&
        (OWN_HOSTS.includes(host) || host.endsWith(OWN_DEPLOY_HOST_SUFFIX));
}

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

        let parsed;
        try {
            parsed = new URL(url);
        } catch (e) {
            return {
                statusCode: 400,
                body: JSON.stringify({ error: 'Invalid URL' })
            };
        }

        const isDev = process.env.CONTEXT === 'dev';
        // External feeds must match the listed URL exactly, so no other path
        // on those sites can be reached through here.
        if (!isOwnFeed(parsed, isDev) && !externalFeedUrls.has(url)) {
            console.warn(`Rejected feed preview URL: ${url}`);
            return {
                statusCode: 403,
                body: JSON.stringify({ error: 'Only ComicCaster feeds and listed external feeds can be previewed' })
            };
        }

        // Handle local development URLs
        let feedUrl = parsed.toString();
        if (isDev && OWN_HOSTS.includes(parsed.hostname)) {
            // In local development, replace production URL with localhost
            feedUrl = `http://localhost:8888${parsed.pathname}`;
            console.log('Rewriting URL for local development:', feedUrl);
        }

        // Fetch it ourselves rather than with parser.parseURL, which follows
        // redirects: a listed feed that redirected could send us anywhere.
        const response = await fetch(feedUrl, {
            redirect: 'manual',
            headers: {
                'User-Agent': 'ComicCaster feed preview (+https://comiccaster.xyz)',
                'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8'
            }
        });
        if (!response.ok) {
            throw new Error(`Feed request returned HTTP ${response.status}`);
        }

        // Parse the feed
        const feed = await parser.parseString(await response.text());

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
