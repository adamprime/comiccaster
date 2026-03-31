# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in ComicCaster, please report it through GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/adamprime/comiccaster/security) of this repository
2. Click **"Report a vulnerability"**
3. Provide a description of the issue, steps to reproduce, and any potential impact

Please **do not** open a public issue for security vulnerabilities.

## Response Timeline

- **Acknowledgment:** Within 48 hours of your report
- **Critical fixes:** Within 14 days
- **Non-critical fixes:** Addressed in the next regular maintenance cycle

## Scope

The following are considered in scope for security reports:

- Cross-site scripting (XSS) or injection vulnerabilities in the web interface
- Credential or secret exposure in code, logs, or configuration
- Vulnerabilities in dependencies that affect ComicCaster's deployment
- Issues that could compromise the Netlify deployment or build pipeline
- Server-side request forgery (SSRF) or path traversal in serverless functions

The following are **out of scope:**

- The content of comic feeds (publicly available material aggregated via RSS)
- Rate limiting or availability of third-party comic source websites
- Issues that require physical access to the build machine
- Findings from automated scanners without a demonstrated impact

## Supported Versions

Only the latest version on the `main` branch is actively maintained. There are no prior releases or version branches.

## Disclosure

We follow coordinated disclosure. Once a fix is available, we'll credit the reporter (unless they prefer to remain anonymous) and publish details in the commit history.
