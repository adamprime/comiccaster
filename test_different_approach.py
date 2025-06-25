#!/usr/bin/env python3
"""
Test different approaches to get the correct daily comic.
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
import time
from bs4 import BeautifulSoup

def test_different_approaches():
    """Test different browser configurations and timing."""
    
    approaches = [
        ("Standard headless", True, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
        ("Non-headless", False, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
        ("Chrome user agent", True, "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ]
    
    for name, headless, user_agent in approaches:
        print(f"\n=== Testing: {name} ===")
        
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument(f"--user-agent={user_agent}")
        
        driver = webdriver.Firefox(options=options)
        
        try:
            url = 'https://www.gocomics.com/bloomcounty'
            driver.get(url)
            
            # Wait longer and check at different intervals
            for wait_time in [5, 10, 15]:
                time.sleep(5)  # Wait 5 more seconds each iteration
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Look for fetchpriority images
                priority_imgs = soup.find_all('img', attrs={'fetchpriority': 'high'})
                
                print(f"  After {wait_time}s wait: Found {len(priority_imgs)} fetchpriority='high' images")
                
                if priority_imgs:
                    for i, img in enumerate(priority_imgs, 1):
                        src = img.get('src', '')
                        hash_part = src.split('/')[-1].split('?')[0] if src else 'none'
                        print(f"    Priority image {i}: {hash_part}")
                        
                        # Check if this is the correct comic (not the wrong one we keep getting)
                        wrong_hash = 'd1259d807c5e0135ec56005056a9545d'
                        if hash_part != wrong_hash:
                            print(f"    ✅ Found different image - this might be correct!")
                            return hash_part
                    break
            else:
                print(f"  ❌ No fetchpriority='high' images found with {name}")
                
        except Exception as e:
            print(f"  Error with {name}: {e}")
        finally:
            driver.quit()
    
    return None

if __name__ == "__main__":
    result = test_different_approaches()
    if result:
        print(f"\n🎉 Found potentially correct comic: {result}")
    else:
        print(f"\n❌ All approaches failed to find fetchpriority='high' images")