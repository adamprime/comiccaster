# Contributing to ComicCaster

Thank you for your interest in contributing to ComicCaster! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Please be respectful and considerate of others when contributing to this project.

## How to Contribute

1. Fork the repository
2. Create a new branch for your feature/fix
3. Make your changes
4. Test your changes
5. Submit a pull request

## Suggesting an External RSS feed

The External RSS tab lists independent webcomics that publish their own RSS
feed. ComicCaster links straight to the publisher's feed and hosts nothing. The
list is curated, so a comic has to meet all of these:

- **It's the comic's own feed.** The creator or the comic's official site
  publishes it, over HTTPS. A mirror, or a feed someone else generates from the
  site, doesn't count.
- **The comic is established.** It has a real archive, built up on a regular
  schedule. A new series, or a handful of posts, doesn't qualify yet. A
  finished comic with its full archive is fine.
- **It isn't advertising.** A comic whose purpose is to promote a product,
  service or platform isn't listed, however well it's made.
- **It isn't sexually explicit.**

Creators are welcome to suggest their own comic. The same bar applies.

To add one, put an entry in `public/external_comics_list.json`, in alphabetical
order:

```json
{
  "name": "Comic Name",
  "slug": "comic-name",
  "author": "Creator Name",
  "url": "https://comic.example/",
  "feed_url": "https://comic.example/feed.xml",
  "source": "external-rss"
}
```

Then rebuild the catalog and run the tests:

```bash
python scripts/generate_catalog.py
pytest -v
```

Commit both `public/external_comics_list.json` and `public/catalog.json`. A
test fails if the committed catalog doesn't match the comic lists.

## Development Setup

1. Clone your fork:
```bash
git clone https://github.com/your-username/comiccaster.git
cd comiccaster
```

2. Set up the development environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file:
```bash
cp .env.example .env
```

## Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the documentation if you're changing functionality
3. The PR will be merged once you have a maintainer's approval
4. Make sure all tests pass before submitting

## Testing

- Run the test suite before submitting changes
- Add tests for new features
- Ensure all tests pass locally

## Style Guide

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and small
- Use type hints where possible

## Documentation

- Update documentation for any changed functionality
- Add docstrings to new functions
- Keep the README up to date
- Document any new dependencies

## Questions?

Feel free to open an issue if you have any questions about contributing. 