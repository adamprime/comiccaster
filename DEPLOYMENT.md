# Deployment Guide

This guide provides detailed instructions for deploying ComicCaster to production.

## Prerequisites

- A GitHub account
- A Netlify account
- A custom domain (optional)
- Python 3.8 or higher
- Node.js 14 or higher (for Netlify functions)

## Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/comiccaster.git
cd comiccaster
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run tests:
```bash
pytest
```

## GitHub Setup

1. Create a new repository on GitHub
2. Push your code:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/comiccaster.git
git push -u origin main
```

3. Enable GitHub Actions:
   - Go to repository Settings > Actions > General
   - Enable "Allow all actions and reusable workflows"
   - Save changes

4. Set up Dependabot:
   - Go to repository Settings > Code security and analysis
   - Enable Dependabot
   - The configuration is already in `.github/dependabot.yml`

## Netlify Deployment

1. Sign up for Netlify and connect your GitHub account

2. Create a new site:
   - Click "New site from Git"
   - Choose your GitHub repository
   - Select the main branch

3. Configure build settings:
   - Build command: `npm install -g netlify-cli && netlify build`
   - Publish directory: `public`
   - Node version: 14 (or higher)

4. Set up environment variables:
   - Go to Site settings > Build & deploy > Environment
   - Add the following variables:
     - `GITHUB_TOKEN`: Your GitHub personal access token with repo access
     - `SECRET_KEY`: A secure random string for session management

5. Configure Netlify Functions:
   - The functions are in the `functions` directory
   - They will be automatically deployed
   - Make sure the function timeout is set to at least 10 seconds

## Custom Domain Setup

1. Purchase a domain (if you don't have one)

2. Add the domain in Netlify:
   - Go to Site settings > Domain management
   - Click "Add custom domain"
   - Enter your domain name

3. Configure DNS:
   - If using Netlify DNS:
     - Add the domain in Netlify
     - Update your domain registrar's nameservers
   - If using external DNS:
     - Add the following records:
       ```
       Type  Name  Value
       A     @     Netlify's IP
       CNAME www   your-site.netlify.app
       ```

4. Enable HTTPS:
   - Netlify will automatically provision an SSL certificate
   - Wait for DNS propagation (can take up to 24 hours)

## Monitoring and Maintenance

1. GitHub Actions:
   - Daily feed updates run at 1 AM UTC
   - Check Actions tab for any failures
   - Failed runs will create GitHub issues

2. Dependabot:
   - Weekly dependency updates
   - Review and merge PRs as needed
   - Test after major updates

3. Logs:
   - Check Netlify logs for function errors
   - Monitor GitHub Actions logs
   - Review error notifications

## Troubleshooting

1. Feed Update Failures:
   - Check GitHub Actions logs
   - Verify GITHUB_TOKEN permissions
   - Check for rate limiting

2. Function Errors:
   - Check Netlify function logs
   - Verify environment variables
   - Check function timeout settings

3. DNS Issues:
   - Verify DNS records
   - Check SSL certificate status
   - Wait for DNS propagation

## Security Considerations

1. Tokens:
   - Tokens expire after 7 days
   - Old tokens are automatically cleaned up
   - Use secure random generation

2. Environment Variables:
   - Never commit .env file
   - Use strong SECRET_KEY
   - Rotate GITHUB_TOKEN periodically

3. Dependencies:
   - Keep dependencies updated
   - Review security advisories
   - Test after updates

## Backup and Recovery

1. Code:
   - GitHub repository serves as backup
   - Regular commits preserve history
   - Consider branch protection rules

2. Data:
   - Feeds are regenerated daily
   - Tokens are temporary
   - No persistent data to backup

3. Configuration:
   - Document all environment variables
   - Keep deployment settings in version control
   - Document custom DNS settings 