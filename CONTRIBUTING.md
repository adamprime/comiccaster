# Contributing to RSS Comics

Thank you for your interest in contributing to RSS Comics! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Please be respectful and considerate of others when contributing to this project.

## How to Contribute

1. Fork the repository
2. Create a new branch for your feature/fix
3. Make your changes
4. Test your changes
5. Submit a pull request

## Development Setup

1. Clone your fork:
```bash
git clone https://github.com/your-username/rss-comics.git
cd rss-comics
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