#!/usr/bin/env python3
"""
Test script to diagnose cookie loading issues on the droplet.
"""
import os
import sys
import pickle
from pathlib import Path

def test_cookies():
    cookie_file = Path(os.environ.get('COMICSKINGDOM_COOKIE_FILE', 'data/comicskingdom_cookies.pkl'))
    
    print("="*80)
    print("COOKIE DIAGNOSTICS")
    print("="*80)
    
    # Check if file exists
    print(f"\n1. Cookie file path: {cookie_file}")
    print(f"   Absolute path: {cookie_file.resolve()}")
    print(f"   Exists: {cookie_file.exists()}")
    
    if not cookie_file.exists():
        print("\n❌ Cookie file not found!")
        return False
    
    # Check file info
    stat_info = cookie_file.stat()
    print(f"\n2. File info:")
    print(f"   Size: {stat_info.st_size} bytes")
    print(f"   Modified: {stat_info.st_mtime}")
    
    # Try to load cookies
    print(f"\n3. Loading cookies...")
    try:
        with open(cookie_file, 'rb') as f:
            cookies = pickle.load(f)
        print(f"   ✅ Successfully loaded {len(cookies)} cookies")
        
        # Print cookie details (without sensitive values)
        print(f"\n4. Cookie details:")
        for i, cookie in enumerate(cookies[:5]):  # Show first 5
            print(f"   Cookie {i+1}:")
            print(f"      Name: {cookie.get('name', 'N/A')}")
            print(f"      Domain: {cookie.get('domain', 'N/A')}")
            print(f"      Path: {cookie.get('path', 'N/A')}")
            print(f"      Secure: {cookie.get('secure', False)}")
            print(f"      HttpOnly: {cookie.get('httpOnly', False)}")
            if 'expiry' in cookie:
                from datetime import datetime
                expiry = datetime.fromtimestamp(cookie['expiry'])
                print(f"      Expires: {expiry}")
        
        if len(cookies) > 5:
            print(f"   ... and {len(cookies) - 5} more cookies")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error loading cookies: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_cookies()
    sys.exit(0 if success else 1)
