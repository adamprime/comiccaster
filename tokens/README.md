# Tokens Directory

This directory contains JSON files for user-generated tokens. Each token file is named with the token UUID and contains information about the comics selected by the user.

## Token File Format

Each token file is a JSON file with the following structure:

```json
{
  "comics": ["comic-slug-1", "comic-slug-2", "comic-slug-3"],
  "created_at": "2023-04-06T12:00:00.000Z"
}
```

- `comics`: An array of comic slugs that the user has selected
- `created_at`: The ISO timestamp when the token was created

## Usage

These token files are used by the Netlify functions to generate combined feeds based on user selections. The files are created when a user selects comics and generates a custom feed.

## Maintenance

Token files are automatically created and managed by the application. No manual intervention is required. 