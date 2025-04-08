#!/usr/bin/env python3
"""
RSS Comics - Main script
"""

import argparse
import json
import os
import sys
from pathlib import Path

def load_config():
    """Load configuration from config.json"""
    config_path = Path("config/config.json")
    if not config_path.exists():
        print("Error: config.json not found. Please copy config.json.template to config.json and edit it.")
        sys.exit(1)
    
    with open(config_path) as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="RSS Comics - Generate RSS feeds for GoComics")
    parser.add_argument("--update", action="store_true", help="Update all feeds")
    parser.add_argument("--config", help="Path to config file", default="config/config.json")
    
    args = parser.parse_args()
    
    if args.update:
        config = load_config()
        print("Updating feeds...")
        # TODO: Implement feed update logic
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 