// Simple serverless function that provides information about available feeds
// instead of trying to run the Flask app which isn't supported in this environment

exports.handler = async function(event, context) {
  // Get base URL
  const host = event.headers.host || 'comiccaster.xyz';
  const protocol = event.headers['x-forwarded-proto'] || 'https';
  const baseUrl = `${protocol}://${host}`;
  
  // Path for debugging
  const path = event.path;
  console.log('Request path:', path);
  
  // Return a static page with RSS feed info
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'text/html',
      'Cache-Control': 'public, max-age=300' // Cache for 5 minutes
    },
    body: `
      <!DOCTYPE html>
      <html lang="en">
      <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>ComicCaster - RSS feeds for your favorite comics</title>
          <style>
              :root {
                  --background-color: #1a1a1a;
                  --text-color: #ffffff;
                  --border-color: #333333;
                  --accent-color: #e91e63;
                  --link-color: #3b82f6;
                  --button-color: #0066cc;
              }

              body {
                  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                  line-height: 1.5;
                  margin: 0;
                  padding: 20px;
                  background: var(--background-color);
                  color: var(--text-color);
              }

              .container {
                  max-width: 1200px;
                  margin: 0 auto;
              }

              .header {
                  text-align: center;
                  margin-bottom: 2rem;
              }

              .header h1 {
                  font-size: 2.5rem;
                  margin-bottom: 0.5rem;
              }

              .header p {
                  font-size: 1.2rem;
                  color: #888;
                  margin: 0;
              }

              .card {
                  background: var(--background-color);
                  border: 1px solid var(--border-color);
                  border-radius: 8px;
                  margin-bottom: 2rem;
                  overflow: hidden;
                  padding: 1.5rem;
              }

              .search-box {
                  margin: 1rem 0;
                  display: flex;
                  gap: 0.5rem;
              }

              .search-box input {
                  flex: 1;
                  padding: 0.5rem;
                  font-size: 1rem;
                  border: 1px solid var(--border-color);
                  border-radius: 4px;
                  background: #333;
                  color: #fff;
              }

              .search-box button {
                  padding: 0.5rem 1rem;
                  font-size: 1rem;
                  background: var(--button-color);
                  color: white;
                  border: none;
                  border-radius: 4px;
                  cursor: pointer;
              }

              .comics-list {
                  max-height: 500px;
                  overflow-y: auto;
                  border: 1px solid var(--border-color);
                  border-radius: 4px;
                  margin-top: 1rem;
              }

              .comics-table {
                  width: 100%;
                  border-collapse: collapse;
              }

              .comics-table th,
              .comics-table td {
                  padding: 0.75rem;
                  text-align: left;
                  border-bottom: 1px solid var(--border-color);
              }

              .comics-table th {
                  background: #222;
                  position: sticky;
                  top: 0;
                  z-index: 10;
              }

              .comics-table tr:hover {
                  background: #222;
              }

              .btn {
                  display: inline-block;
                  padding: 0.5rem 1rem;
                  font-size: 1rem;
                  font-weight: 500;
                  text-align: center;
                  text-decoration: none;
                  border-radius: 4px;
                  cursor: pointer;
                  transition: background-color 0.2s;
                  border: none;
                  background-color: var(--button-color);
                  color: white;
                  margin-top: 1rem;
              }

              .btn:hover {
                  background-color: #0052a3;
              }

              a {
                  color: var(--link-color);
                  text-decoration: none;
              }

              a:hover {
                  text-decoration: underline;
              }

              .footer {
                  text-align: center;
                  margin-top: 40px;
                  padding-top: 20px;
                  border-top: 1px solid #444;
                  color: #999;
              }

              .popular-feeds {
                  display: grid;
                  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                  gap: 1rem;
                  margin-top: 1rem;
              }

              .feed-card {
                  padding: 1rem;
                  border: 1px solid var(--border-color);
                  border-radius: 4px;
                  text-align: center;
              }

              .feed-card:hover {
                  border-color: var(--link-color);
              }

              code {
                  background: #333;
                  padding: 0.2rem 0.4rem;
                  border-radius: 4px;
                  font-family: monospace;
              }

              @media (max-width: 768px) {
                  .popular-feeds {
                      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                  }
              }
          </style>
      </head>
      <body>
          <div class="container">
              <header class="header">
                  <h1>ComicCaster</h1>
                  <p>Read your favorite comics as an RSS feed</p>
              </header>

              <div class="card">
                  <h2>About ComicCaster</h2>
                  <p>ComicCaster is a tool that generates RSS feeds for comics from GoComics, allowing you to read your favorite comics in your preferred RSS reader.</p>
                  
                  <h3>Features:</h3>
                  <ul>
                      <li>Individual RSS feeds for hundreds of comics</li>
                      <li>Daily updates of comic feeds</li>
                      <li>High-quality comic images</li>
                  </ul>
              </div>

              <div class="card">
                  <h2>Find a Comic Feed</h2>
                  <p>Use the search box to find your favorite comics, or browse some popular options below.</p>
                  
                  <div class="search-box">
                      <input type="text" id="search-input" placeholder="Search comics..." aria-label="Search comics">
                      <button id="search-button" type="button">Search</button>
                  </div>

                  <h3>Popular Comics</h3>
                  <div class="popular-feeds">
                      <a href="/rss/calvinandhobbes" class="feed-card">
                          <div>Calvin and Hobbes</div>
                      </a>
                      <a href="/rss/garfield" class="feed-card">
                          <div>Garfield</div>
                      </a>
                      <a href="/rss/peanuts" class="feed-card">
                          <div>Peanuts</div>
                      </a>
                      <a href="/rss/dilbert-classics" class="feed-card">
                          <div>Dilbert Classics</div>
                      </a>
                      <a href="/rss/luann" class="feed-card">
                          <div>Luann</div>
                      </a>
                      <a href="/rss/foxtrot" class="feed-card">
                          <div>FoxTrot</div>
                      </a>
                      <a href="/rss/pearlsbeforeswine" class="feed-card">
                          <div>Pearls Before Swine</div>
                      </a>
                      <a href="/rss/doonesbury" class="feed-card">
                          <div>Doonesbury</div>
                      </a>
                  </div>
              </div>

              <div class="card">
                  <h2>How to Use</h2>
                  <p>To subscribe to a comic in your RSS reader, use a URL in this format:</p>
                  <code>${baseUrl}/rss/comic-slug</code>
                  <p>For example, to subscribe to Calvin and Hobbes:</p>
                  <a href="${baseUrl}/rss/calvinandhobbes">${baseUrl}/rss/calvinandhobbes</a>
                  <p>The "comic-slug" is the name that appears in the GoComics URL for that comic.</p>
              </div>

              <footer class="footer">
                  <p>Powered by <a href="https://github.com/adamprime/comiccaster">ComicCaster</a></p>
              </footer>
          </div>

          <script>
              document.addEventListener('DOMContentLoaded', function() {
                  const searchInput = document.getElementById('search-input');
                  const searchButton = document.getElementById('search-button');
                  
                  // Handle search
                  function handleSearch() {
                      const query = searchInput.value.trim().toLowerCase();
                      if (query) {
                          // Convert spaces to hyphens and remove special characters
                          const slug = query.replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
                          window.location.href = '/rss/' + slug;
                      }
                  }
                  
                  // Event listeners
                  searchButton.addEventListener('click', handleSearch);
                  searchInput.addEventListener('keypress', function(e) {
                      if (e.key === 'Enter') {
                          handleSearch();
                      }
                  });
              });
          </script>
      </body>
      </html>
    `
  };
}; 