# Custom Combined Feed Feature Specification

## Overview

The goal is to allow users to generate a personalized, combined RSS feed of their favorite GoComics. This feed is created on demand without requiring user accounts. Once generated, the feed is static—users receive a unique URL (which can optionally be emailed to them) that they can subscribe to, but it can’t be edited. If users wish to update their selection, they simply generate a new feed.

## Requirements

- **User Selection:**  
  Users can choose from the available comics (e.g., Pickles, Pearls Before Swine, Calvin and Hobbes) via a simple interface.
  
- **Stateless Generation:**  
  No account or persistent user storage is required. The user’s comic selection is encoded directly into the feed URL.
  
- **Unique & Unguessable URLs:**  
  The generated feed URL should be unique. This can be achieved by encoding the selection (e.g., as query parameters) or by generating a random token. If privacy is a concern, using a token with temporary storage may be preferable.
  
- **One-Off Feed:**  
  The feed is generated once and remains static. If a user wants to change their selection, they must generate a new feed.
  
- **Optional Email Notification:**  
  The system may provide the option to email the unique feed URL to the user.

## Architecture

### Components

1. **Comic Selection Interface:**  
   A simple front-end (web page with checkboxes) that displays the list of available comics (retrieved via the JSON-LD “Comics A to Z” loader).  
   
2. **URL Generation Mechanism:**  
   - **Option A:** Encode the selected comic slugs directly in URL query parameters (e.g., `?comics=pickles,pearlsbeforeswine,calvinandhobbes`).  
   - **Option B:** Generate a random, unguessable token that maps to the user’s selection in temporary storage (for enhanced privacy).  
   
3. **Feed Aggregator Service:**  
   - Reads the user’s selection from the URL (or from temporary storage if using tokens).  
   - Fetches the latest entries from each individual per-comic RSS feed.  
   - Merges the entries in chronological order.  
   - Generates a combined RSS feed using a tool like `feedgen`.
   
4. **Delivery & Notification:**  
   - The combined feed is served via a unique URL.
   - Optionally, the system emails this URL to the user.

5. **Scheduling & Updates:**  
   - The individual per-comic feeds are updated on a regular schedule (handled by an existing scraper/scheduler).
   - The aggregator generates the combined feed on-demand, reflecting the latest available comic entries.

## Data Flow

1. **User Selection:**  
   The user selects their desired comics on the interface.

2. **Feed URL Generation:**  
   The system encodes the selected comic slugs (either directly in the URL or via a generated token) and presents the unique feed URL to the user.

3. **Feed Aggregation:**  
   When the unique URL is accessed:
   - The aggregator parses the comic selections.
   - It retrieves the latest entries from each comic’s individual feed.
   - It merges these entries and generates a combined RSS XML feed.

4. **Delivery:**  
   The final RSS feed is served at the generated URL. Users can subscribe to it using any RSS reader.

## Security Considerations

- **Visibility of Selections:**  
  If using query parameters, the selected comics are visible in the URL. This is acceptable if the comic data is non-sensitive.  
- **Tokenization Option:**  
  For greater privacy, consider generating a random token that maps to the selection in a temporary (non-persistent) store.
- **URL Expiry/Re-generation:**  
  Decide whether the custom feed URL should be permanent or have an expiration date. Permanent links are simpler but may require users to regenerate their feed if their interests change.
- **Link Sharing:**  
  Since the feed URL is the only “credential” for accessing the custom feed, ensure that it is unguessable or optionally allow users to revoke it by generating a new feed.

## Implementation Details

- **Backend Language:** Python  
- **Key Libraries:**  
  - `Flask` or `FastAPI` for the aggregator endpoint  
  - `feedgen` for generating RSS feeds  
  - `requests` and `BeautifulSoup` for fetching and parsing per-comic feeds  
  - `json` and `re` for handling the JSON-LD and URL encoding  
- **Front-End:**  
  A minimal HTML page to display the list of comics (via checkboxes) and generate the unique feed URL.
- **Deployment:**  
  Containerize the application using Docker. Use cron jobs or APScheduler to update per-comic feeds. Host the combined feed on a static server or lightweight web service.
- **Optional Email Integration:**  
  Integrate with an email service (like SendGrid or Amazon SES) to send the feed URL to users.

## User Experience

- The user visits the comic selection page, sees a list of comics (derived from the “Comics A to Z” source), and selects their favorites.
- Upon submission, the system displays a unique RSS feed URL (e.g., `https://example.com/combined?comics=pickles,pearlsbeforeswine`) or a token-based URL.
- The user can copy the URL, subscribe to it in their RSS reader, or have it emailed to them.
- The feed remains static until the user chooses to generate a new one.

## Roadmap

1. **Prototype Aggregator:**  
   Build a minimal aggregator that accepts comic slugs via URL parameters and generates a combined RSS feed.
2. **Comic Selection Interface:**  
   Create a simple web page that presents the available comics and outputs the corresponding feed URL.
3. **Email Notification Module:**  
   Integrate an optional email service to send feed URLs.
4. **Tokenization (Optional):**  
   Explore generating unguessable tokens to enhance feed privacy.
5. **Testing & Deployment:**  
   Test performance, security, and scalability. Deploy the service using Docker and scheduled tasks.
6. **Documentation & UX Guidelines:**  
   Provide clear instructions for users on how to generate, use, and regenerate their custom combined feeds.

---

This specification outlines a lightweight, accountless approach to providing custom combined RSS feeds for GoComics. It’s designed to be simple, secure, and user-friendly while allowing flexibility for future enhancements.

Let me know if you’d like any changes or additional details!