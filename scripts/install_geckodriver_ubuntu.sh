#!/bin/bash
# Install geckodriver on Ubuntu/Linux
set -e

GECKODRIVER_VERSION="v0.33.0"
echo "Installing geckodriver ${GECKODRIVER_VERSION}..."

# Download geckodriver
wget -q "https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"

# Extract and install
tar -xzf "geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"
sudo mv geckodriver /usr/local/bin/
sudo chmod +x /usr/local/bin/geckodriver

# Clean up
rm "geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"

echo "Geckodriver installed successfully!"
geckodriver --version
