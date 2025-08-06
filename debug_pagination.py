#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HLTV Pagination Debug Script
Purpose: Analyze HLTV pagination structure to understand the limits
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs


def debug_pagination():
    """Debug HLTV pagination structure"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    # Test different URLs to understand pagination
    test_urls = [
        "https://www.hltv.org/players",
        "https://www.hltv.org/players/A",
        "https://www.hltv.org/players/A?offset=52",
        "https://www.hltv.org/players/A?offset=104",
        "https://www.hltv.org/players/A?offset=520",  # High offset to test limits
        "https://www.hltv.org/players/A?offset=1040", # Very high offset
    ]
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"Testing URL: {url}")
        print('='*80)
        
        try:
            response = session.get(url, timeout=15)
            print(f"Status Code: {response.status_code}")
            print(f"Response Size: {len(response.content)} bytes")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for player nicknames
                nickname_selectors = [
                    '.players-archive-nickname.text-ellipsis',
                    '.players-archive-nickname',
                    'div[class*="nickname"]',
                ]
                
                total_nicknames = 0
                for selector in nickname_selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"Found {len(elements)} nicknames using selector: {selector}")
                        total_nicknames = len(elements)
                        # Show first few nicknames
                        for i, elem in enumerate(elements[:5]):
                            nickname = elem.get_text(strip=True)
                            print(f"  {i+1}. {nickname}")
                        if len(elements) > 5:
                            print(f"  ... and {len(elements) - 5} more")
                        break
                
                if total_nicknames == 0:
                    print("No nicknames found - page might be empty or structure changed")
                    # Let's look at the page content to understand why
                    print("\nAnalyzing page content...")
                    
                    # Check for common indicators of empty pages
                    page_text = soup.get_text().lower()
                    if 'no players found' in page_text:
                        print("Found 'no players found' message")
                    elif 'error' in page_text:
                        print("Found 'error' message")
                    elif len(page_text) < 1000:
                        print(f"Page content very short ({len(page_text)} chars) - likely empty")
                    
                    # Look for any player-related content
                    player_links = soup.find_all('a', href=re.compile(r'/player/\d+'))
                    if player_links:
                        print(f"Found {len(player_links)} player links")
                        for i, link in enumerate(player_links[:3]):
                            print(f"  Link {i+1}: {link.get('href')}")
                
                # Look for pagination elements
                print(f"\nPagination analysis:")
                pagination_links = soup.find_all('a', href=re.compile(r'offset=\d+'))
                if pagination_links:
                    print(f"Found {len(pagination_links)} pagination links:")
                    offsets = []
                    for link in pagination_links[:10]:  # Show first 10
                        href = link.get('href')
                        match = re.search(r'offset=(\d+)', href)
                        if match:
                            offset = int(match.group(1))
                            offsets.append(offset)
                            print(f"  Offset: {offset}, Link: {href}")
                    
                    if offsets:
                        print(f"Offset range: {min(offsets)} - {max(offsets)}")
                else:
                    print("No pagination links found")
                
                # Check for "Next" or "More" buttons
                next_buttons = soup.find_all(['a', 'button'], text=re.compile(r'next|more', re.I))
                if next_buttons:
                    print(f"Found {len(next_buttons)} next/more buttons")
                    for btn in next_buttons:
                        print(f"  Button: {btn.get_text(strip=True)}, href: {btn.get('href', 'N/A')}")
                
            else:
                print(f"Failed to fetch page: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"Error testing URL: {e}")
        
        time.sleep(2)  # Be respectful
    
    print(f"\n{'='*80}")
    print("Debug completed!")


if __name__ == "__main__":
    debug_pagination()