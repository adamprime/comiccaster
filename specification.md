# GoComics RSS Feed Generator Specification

## 1. Project Overview

**Goal:**  
- **Phase 1:** Create an individual RSS feed for each comic on GoComics (like Pickles, Pearls Before Swine, Calvin and Hobbes, etc.) by scraping each comic's daily page.  
- **Phase 2:** Build a personalization layer where a user can select which comics they follow and generate a combined RSS feed tailored to their tastes, similar to [ComicsRSS.com](https://www.comicsrss.com/).

---

## 2. Architecture Diagram

```plaintext
                +----------------------+
                |  Comics A-to-Z Loader|
                | (JSON-LD Parser)     |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |  Comic Scraper Module|
                | (per-comic scraper)  |
                +----------+-----------+
                           |
         +-----------------+-----------------+
         |                                   |
         v                                   v
+-------------------+            +----------------------+
|  Feed Generator   |            |   Feed Aggregator    |
| (Per-Comic RSS)   |            | (Personalized RSS)   |
+--------+----------+            +---------+------------+
         |                                   |
         v                                   v
+-------------------+            +----------------------+
|   Storage/DB      | <--------->|  Web Interface      |
| (RSS files or     |            | (Select comics &     |
|  Static Hosting)  |            |  generate feeds)     |
+-------------------+            +----------------------+
```

## 3. Core Modules

A. Comics A-to-Z Loader
	•	Purpose:
Parse the "Comics A to Z" page's JSON-LD block to extract the full list of comics (their names and URLs).
	•	Outcome:
Produce a master list of comic slugs (e.g., "pickles", "pearlsbeforeswine") available for scraping.

B. Comic Scraper Module
	•	Purpose:
For each comic slug, fetch the daily page (e.g., https://www.gocomics.com/pickles) and extract metadata like the comic image URL (using the og:image meta tag), title, and publication date.
	•	Key Technique:
Meta Piggybacking: Leverage the Open Graph metadata (e.g., <meta property="og:image">) for a robust and stable extraction method.

C. Feed Generator (Per-Comic)
	•	Purpose:
Generate a valid RSS feed for each comic.
	•	Structure:
Each feed entry includes:
	•	Title (e.g., "Pickles – 2025-04-06")
	•	Link to the comic's page
	•	Publication date
	•	Description containing the comic image (embedded as HTML)
	•	Libraries:
Use Python's feedgen library for RSS generation.

D. Feed Aggregator
	•	Purpose:
Combine multiple individual comic feeds into a single personalized feed.
	•	Features:
	•	Merge entries from selected feeds chronologically
	•	Add comic slugs as categories for easy filtering
	•	Limit the number of entries (default: 50)
	•	Implementation:
	•	Use feedgen library for feed generation
	•	Parse individual feeds using ElementTree
	•	Sort entries by publication date

E. Web Interface
	•	Purpose:
Provide a user-friendly interface for selecting comics and generating feeds.
	•	Features:
	•	Display available comics with search functionality
	•	Select multiple comics with "Select All" option
	•	Generate unique feed URLs using tokens
	•	Optional email notification with feed URL
	•	Implementation:
	•	Use Flask for the web framework
	•	Bootstrap for responsive design
	•	Flask-Mail for email notifications
	•	In-memory token storage (30-day expiry)

F. Scheduler & Deployment
	•	Purpose:
Automate the scraping and feed generation process daily (or at a specified interval).
	•	Tools:
	•	Use cron jobs or Python's APScheduler.
	•	Package the application in a Docker container for easy deployment.
	•	Output:
Save each per-comic RSS feed to a location that's served statically (e.g., via GitHub Pages, S3, or a small web server).

## 4. Tech Stack
|         Task       |       Technology / Library     |
|:------------------:|:------------------------------:|
|   HTTP Requests    |   requests                     |
|   HTML Parsing     |   BeautifulSoup                |
|   JSON Parsing     |   Python's json module         |
|   RSS Generation   |   feedgen                      |
|   Web Framework    |   Flask                        |
|   Email Service    |   Mailgun                      |
|   Scheduling       |   cron or APScheduler          |
|   Frontend         |   Bootstrap 5                  |
|   Deployment       |   Docker, GitHub Pages, or S3  |

## 5. User Stories
	•	As a user, I want to subscribe to an individual RSS feed for my favorite comic (e.g., Pickles) so that I receive daily updates.
	•	As a user, I want to pick a set of comics I follow and get a combined feed that aggregates all their daily updates.
	•	As a user, I want to search through the list of available comics to find my favorites quickly.
	•	As a user, I want to receive my personalized feed URL via email for easy access.
	•	As a developer, I want the system to automatically update feeds daily so that the RSS entries remain current without manual intervention.
	•	As a developer, I want to leverage robust metadata (via the og:image tag) to minimize maintenance when GoComics updates its site layout.

## 6. Workflow
	1.	Initialization:
	•	Use the Comics A-to-Z Loader to generate the list of available comics.
	•	Start the web server to serve the user interface.
	2.	User Interaction:
	•	User visits the web interface and searches/selects their desired comics.
	•	System generates a unique token and creates a personalized feed URL.
	•	User is presented with the feed URL and instructed to save it.
	3.	Feed Generation:
	•	When a user accesses their feed URL, the system:
	•	Validates the token
	•	Retrieves the selected comics
	•	Aggregates the feeds
	•	Returns the combined feed in RSS format
	4.	Maintenance:
	•	Daily updates of individual comic feeds
	•	Cleanup of expired tokens (after 30 days)

## 7. Next Steps / Roadmap
	1.	Phase 1: Build Per-Comic Feeds ✓
	•	Develop the scraper and feed generator for a single comic
	•	Expand to handle multiple comics (using the A-to-Z loader)
	2.	Phase 2: Feed Aggregation ✓
	•	Implement the feed aggregator
	•	Add support for combining multiple feeds
	3.	Phase 3: Web Interface ✓
	•	Create a user-friendly interface for comic selection
	•	Implement feed URL generation and email notifications
	4.	Phase 4: Deployment & Automation
	•	Containerize the application
	•	Set up scheduling (via cron or APScheduler)
	•	Deploy to a hosting platform
	5.	Optional Enhancements:
	•	Add user accounts for saving preferences
	•	Implement feed caching for better performance
	•	Add analytics for tracking popular comics

## 8. User Experience & CLI/Deployment Considerations
	•	CLI Tool:
A simple command like python comiccaster.py --update can trigger a full update.
	•	Web Interface:
Access via http://localhost:5000 for comic selection and feed generation.
	•	Deployment:
Use Docker for containerization and GitHub Actions or a cron job on a VM for scheduling updates.

## Implementation Details

### Feed URL Generation and Display

The application generates unique feed URLs for users based on their comic selections:

1. **Token Generation**:
   - Each feed URL contains a unique token (UUID)
   - Tokens are stored in memory with a 30-day expiration
   - Tokens map to the user's comic selections

2. **Feed Display**:
   - The feed URL is displayed only once after generation
   - Users are instructed to save the URL as it won't be shown again
   - A copy button is provided for easy copying

3. **Security Considerations**:
   - Tokens are randomly generated and unguessable
   - Tokens expire after 30 days to prevent stale feeds
   - No personal information is collected or stored

## Summary

This project provides:
	•	Individual RSS feeds for GoComics comics
	•	A web interface for selecting and combining feeds
	•	Search functionality for finding comics
	•	Token-based feed URLs for privacy
	•	Automatic daily updates