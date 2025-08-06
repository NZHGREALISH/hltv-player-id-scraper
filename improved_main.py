#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HLTV Player Nickname Scraper - Improved Version
Function: Scrape all player nicknames from https://www.hltv.org/players with better pagination handling
Author: Python Web Scraping Engineer
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
from typing import Set, List, Dict, Optional
import logging
import os
from urllib.parse import urljoin, urlparse, parse_qs


class HLTVPlayerScraper:
    """Improved HLTV Player Nickname Scraper Class"""
    
    def __init__(self):
        """Initialize the scraper"""
        self.base_url = "https://www.hltv.org/players"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.player_nicknames: Set[str] = set()
        self.visited_urls: Set[str] = set()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('hltv_scraper_improved.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def request_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """
        Request function with retry mechanism and better error handling
        
        Args:
            url: The URL to request
            max_retries: Maximum number of retries
            
        Returns:
            requests.Response or None if failed
        """
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"Requesting: {url} (attempt {attempt + 1})")
                response = self.session.get(url, timeout=20)
                
                # Check if page is actually empty or has no content
                if response.status_code == 404:
                    self.logger.warning(f"Page not found (404): {url}")
                    return None
                
                response.raise_for_status()
                
                # Additional check: if response is too small, it might be empty
                if len(response.content) < 1000:
                    self.logger.warning(f"Response too small ({len(response.content)} bytes), might be empty page: {url}")
                    return None
                    
                return response
                
            except requests.RequestException as e:
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 3  # Longer wait time
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    self.logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Final request failure after {max_retries + 1} attempts: {e}")
                    return None

    def extract_player_nicknames_from_page(self, page_content: str) -> List[str]:
        """
        Extract player nicknames from page content with multiple fallback methods
        """
        soup = BeautifulSoup(page_content, 'html.parser')
        
        # Multiple selectors to try
        nickname_selectors = [
            '.players-archive-nickname.text-ellipsis',  # Primary selector
            '.players-archive-nickname',                 # Backup selector
            'div[class*="nickname"]',                    # Any div with nickname in class
            '.player-nick',                              # Alternative class name
            '.playernick',                               # Another alternative
        ]
        
        nicknames = []
        
        for selector in nickname_selectors:
            elements = soup.select(selector)
            if elements:
                self.logger.debug(f"Found {len(elements)} nicknames using selector: {selector}")
                for element in elements:
                    nickname = element.get_text(strip=True)
                    if nickname and len(nickname) > 0:
                        nicknames.append(nickname)
                break
        
        # If no nicknames found with CSS selectors, try regex as fallback
        if not nicknames:
            self.logger.debug("No nicknames found with CSS selectors, trying regex fallback")
            # Look for patterns that might contain player names
            text_content = soup.get_text()
            # This is a very basic fallback - you might need to adjust based on actual HTML structure
            potential_names = re.findall(r'player/\d+/([^"\'>\s]+)', page_content)
            nicknames.extend(potential_names)
        
        # Remove duplicates while preserving order
        unique_nicknames = []
        seen = set()
        for nickname in nicknames:
            if nickname not in seen:
                unique_nicknames.append(nickname)
                seen.add(nickname)
        
        return unique_nicknames

    def get_pagination_info(self, soup: BeautifulSoup, current_url: str) -> Dict:
        """
        Extract pagination information from the page
        """
        pagination_info = {
            'next_urls': [],
            'has_more': False,
            'total_pages_estimated': 1
        }
        
        # Look for pagination elements
        pagination_selectors = [
            'a[href*="offset="]',
            '.pagination a',
            'a[href*="/players"]',
            '.page-link',
            '.pagination-next'
        ]
        
        all_offsets = set()
        next_urls = set()
        
        for selector in pagination_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                if href and ('offset=' in href or '/players' in href):
                    # Convert relative URLs to absolute
                    full_url = urljoin(current_url, href)
                    
                    # Extract offset value
                    parsed_url = urlparse(full_url)
                    query_params = parse_qs(parsed_url.query)
                    if 'offset' in query_params:
                        try:
                            offset = int(query_params['offset'][0])
                            all_offsets.add(offset)
                            next_urls.add(full_url)
                        except (ValueError, IndexError):
                            continue
        
        # Add URLs for different letters if this is a letter-specific page
        if len(current_url.split('/')) > 4:  # Letter-specific URL
            letter = current_url.split('/')[-1].split('?')[0]
            if letter.isalpha() and len(letter) == 1:
                # Generate next letter URLs
                next_letter = chr(ord(letter) + 1)
                if next_letter <= 'Z':
                    next_letter_url = f"{self.base_url}/{next_letter}"
                    next_urls.add(next_letter_url)
        
        pagination_info['next_urls'] = list(next_urls)
        pagination_info['has_more'] = len(next_urls) > 0
        
        if all_offsets:
            max_offset = max(all_offsets)
            pagination_info['total_pages_estimated'] = (max_offset // 52) + 2  # Rough estimate
        
        return pagination_info

    def scrape_with_adaptive_strategy(self) -> List[str]:
        """
        Adaptive scraping strategy that handles various pagination scenarios
        """
        self.logger.info("Starting adaptive HLTV player nickname scraping...")
        
        # Strategy 1: Try letter-by-letter approach (A-Z)
        urls_to_visit = []
        
        # Add letter-specific URLs
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            urls_to_visit.append(f"{self.base_url}/{letter}")
        
        # Add main players page
        urls_to_visit.insert(0, self.base_url)
        
        processed_count = 0
        max_pages_per_letter = 20  # Safety limit to prevent infinite loops
        
        while urls_to_visit:
            current_url = urls_to_visit.pop(0)
            
            # Skip if already visited
            if current_url in self.visited_urls:
                continue
                
            self.visited_urls.add(current_url)
            processed_count += 1
            
            self.logger.info(f"Processing URL {processed_count}: {current_url}")
            
            # Make request
            response = self.request_with_retry(current_url)
            if not response:
                self.logger.warning(f"Failed to fetch: {current_url}")
                continue
            
            # Extract nicknames
            page_nicknames = self.extract_player_nicknames_from_page(response.text)
            
            if page_nicknames:
                old_count = len(self.player_nicknames)
                self.player_nicknames.update(page_nicknames)
                new_count = len(self.player_nicknames)
                added = new_count - old_count
                
                if added > 0:
                    self.logger.info(f"Found {len(page_nicknames)} nicknames, added {added} new ones. Total: {new_count}")
                    
                    # Get pagination info
                    soup = BeautifulSoup(response.text, 'html.parser')
                    pagination_info = self.get_pagination_info(soup, current_url)
                    
                    # Add new URLs to visit (but limit per letter)
                    letter_pages = sum(1 for url in self.visited_urls if current_url.split('/')[-1].split('?')[0] in url)
                    if letter_pages < max_pages_per_letter:
                        for next_url in pagination_info['next_urls']:
                            if next_url not in self.visited_urls and next_url not in urls_to_visit:
                                urls_to_visit.append(next_url)
                                self.logger.debug(f"Added to queue: {next_url}")
                else:
                    self.logger.info(f"Found {len(page_nicknames)} nicknames, but all were duplicates")
            else:
                self.logger.warning(f"No nicknames found on page: {current_url}")
                # If no nicknames found, this might be an empty page - stop exploring this branch
            
            # Rate limiting
            time.sleep(1.5)  # Slightly longer delay
            
            # Progress update
            if processed_count % 10 == 0:
                self.logger.info(f"Progress: {processed_count} pages processed, {len(self.player_nicknames)} unique nicknames found")
                self.logger.info(f"Remaining URLs in queue: {len(urls_to_visit)}")
        
        # Convert to sorted list
        sorted_nicknames = sorted(list(self.player_nicknames))
        
        self.logger.info(f"Scraping completed! Found {len(sorted_nicknames)} unique player nicknames")
        self.logger.info(f"Processed {processed_count} pages total")
        
        if sorted_nicknames:
            self.logger.info(f"Sample nicknames: {sorted_nicknames[:10]}...")
        
        return sorted_nicknames

    def save_to_files(self, player_nicknames: List[str]) -> None:
        """
        Save player nicknames to multiple file formats
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 1. Save as JSON format
        json_data = {
            'title': 'HLTV Player Nicknames (Improved Scraper)',
            'source_url': self.base_url,
            'total_count': len(player_nicknames),
            'timestamp': timestamp,
            'sample_nicknames': player_nicknames[:10] if player_nicknames else [],
            'scraping_method': 'adaptive_pagination',
            'pages_processed': len(self.visited_urls),
            'player_nicknames': player_nicknames
        }
        
        json_filename = 'hltv_player_nicknames_improved.json'
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # 2. Save as text format
        txt_filename = 'hltv_player_nicknames_improved.txt'
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(f"HLTV Player Nicknames List (Improved)\n")
            f.write(f"{'='*50}\n")
            f.write(f"Source: {self.base_url}\n")
            f.write(f"Total: {len(player_nicknames)} players\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Pages processed: {len(self.visited_urls)}\n")
            if player_nicknames:
                f.write(f"Nickname samples: {', '.join(player_nicknames[:5])}\n")
            f.write(f"{'='*50}\n\n")
            
            for i, nickname in enumerate(player_nicknames, 1):
                f.write(f"{i:4d}. {nickname}\n")
        
        # 3. Save as CSV format
        csv_filename = 'hltv_player_nicknames_improved.csv'
        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write("Number,Player Nickname\n")
            for i, nickname in enumerate(player_nicknames, 1):
                f.write(f"{i},{nickname}\n")
        
        # Output file information
        files_info = []
        for filename in [json_filename, txt_filename, csv_filename]:
            if os.path.exists(filename):
                size = os.path.getsize(filename)
                files_info.append(f"  {filename} ({size} bytes)")
        
        self.logger.info("Files saved successfully:")
        for info in files_info:
            self.logger.info(info)


def main():
    """Main function"""
    print("HLTV Player Nickname Scraper (Improved Version)")
    print("=" * 60)
    print("Features:")
    print("- Adaptive pagination handling")
    print("- Better empty page detection")
    print("- Multiple fallback extraction methods")
    print("- Comprehensive letter-by-letter scraping")
    print("=" * 60)
    
    scraper = HLTVPlayerScraper()
    
    try:
        # Scrape all player nicknames using adaptive strategy
        start_time = time.time()
        player_nicknames = scraper.scrape_with_adaptive_strategy()
        end_time = time.time()
        
        if not player_nicknames:
            print("Failed to get any player nicknames")
            return 1
        
        # Print statistical results
        print(f"\n{'='*60}")
        print(f"HLTV Player Nickname Scraping Results (Improved)")
        print(f"{'='*60}")
        print(f"Total time: {end_time - start_time:.2f} seconds")
        print(f"Total count: {len(player_nicknames):,} unique nicknames")
        print(f"Pages processed: {len(scraper.visited_urls)}")
        print(f"First 10 nicknames: {player_nicknames[:10]}")
        print(f"Last 10 nicknames: {player_nicknames[-10:]}")
        
        # Statistical distribution by letter
        letter_distribution = {}
        for nickname in player_nicknames:
            first_letter = nickname[0].upper() if nickname else '?'
            letter_distribution[first_letter] = letter_distribution.get(first_letter, 0) + 1
        
        print(f"\nDistribution by first letter:")
        for letter in sorted(letter_distribution.keys()):
            count = letter_distribution[letter]
            print(f"  {letter}: {count:,} nicknames")
        
        # Save to files
        scraper.save_to_files(player_nicknames)
        
        print(f"\nScraping task completed!")
        
    except KeyboardInterrupt:
        print("\nUser interrupted the program")
        return 1
    except Exception as e:
        logging.error(f"Program execution failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())