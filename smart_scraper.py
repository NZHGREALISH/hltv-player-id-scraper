#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart HLTV Player Scraper
Solves the high-offset pagination issue by using multiple extraction strategies
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
from typing import Set, List, Dict, Optional
import logging
import os
from urllib.parse import urljoin


class SmartHLTVScraper:
    """Smart HLTV scraper that adapts to different page structures"""
    
    def __init__(self):
        """Initialize the scraper"""
        self.base_url = "https://www.hltv.org/players"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.player_nicknames: Set[str] = set()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('smart_scraper.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def request_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Request with retry mechanism"""
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"Requesting: {url}")
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 2
                    self.logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Final request failure: {e}")
                    return None

    def extract_nicknames_multiple_strategies(self, page_content: str, url: str) -> List[str]:
        """
        Extract nicknames using multiple strategies to handle different page structures
        """
        soup = BeautifulSoup(page_content, 'html.parser')
        nicknames = []
        
        # Strategy 1: Standard CSS selectors (works for normal pages)
        css_selectors = [
            '.players-archive-nickname.text-ellipsis',
            '.players-archive-nickname', 
            'div[class*="nickname"]',
            '.player-nick',
            '.playernick'
        ]
        
        for selector in css_selectors:
            elements = soup.select(selector)
            if elements:
                self.logger.debug(f"Strategy 1 - Found {len(elements)} nicknames using: {selector}")
                for element in elements:
                    nickname = element.get_text(strip=True)
                    if nickname:
                        nicknames.append(nickname)
                break
        
        # Strategy 2: Extract from player URLs (works when CSS fails)
        if not nicknames:
            self.logger.debug("Strategy 1 failed, trying Strategy 2 - extracting from URLs")
            player_links = soup.find_all('a', href=re.compile(r'/player/\d+'))
            for link in player_links:
                href = link.get('href', '')
                # Extract nickname from URL: /player/12345/nickname
                match = re.search(r'/player/\d+/([^/?]+)', href)
                if match:
                    nickname = match.group(1)
                    # Clean up the nickname
                    nickname = nickname.replace('%20', ' ').replace('-', ' ')
                    if nickname and len(nickname) > 1:
                        nicknames.append(nickname)
            
            if nicknames:
                self.logger.debug(f"Strategy 2 - Found {len(nicknames)} nicknames from URLs")
        
        # Strategy 3: Text content analysis (fallback)
        if not nicknames:
            self.logger.debug("Strategy 2 failed, trying Strategy 3 - text analysis")
            # Look for player patterns in the page text
            text_content = soup.get_text()
            
            # Find patterns that look like player names
            # This is a basic pattern - you might need to refine this
            potential_names = re.findall(r'\b[A-Za-z][A-Za-z0-9_.-]{2,15}\b', text_content)
            
            # Filter out common words that aren't player names
            common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'man', 'men', 'run', 'too', 'any', 'big', 'end', 'far', 'got', 'let', 'own', 'put', 'say', 'she', 'try', 'use', 'way', 'win', 'yes', 'yet'}
            
            filtered_names = [name for name in potential_names if name.lower() not in common_words and len(name) > 2]
            
            if filtered_names:
                nicknames.extend(filtered_names[:20])  # Limit to prevent false positives
                self.logger.debug(f"Strategy 3 - Found {len(filtered_names)} potential nicknames")
        
        # Remove duplicates while preserving order
        unique_nicknames = []
        seen = set()
        for nickname in nicknames:
            if nickname not in seen:
                unique_nicknames.append(nickname)
                seen.add(nickname)
        
        return unique_nicknames

    def find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Find the next page URL from pagination"""
        
        # Look for "Next" button
        next_selectors = [
            'a:contains("Next")',
            'a[href*="offset="]',
            '.pagination a',
        ]
        
        for selector in next_selectors:
            if 'contains' in selector:
                # Handle contains selector manually
                links = soup.find_all('a', string=re.compile(r'next', re.I))
            else:
                links = soup.select(selector)
            
            for link in links:
                href = link.get('href', '')
                if href and 'offset=' in href:
                    return urljoin(current_url, href)
        
        return None

    def scrape_single_letter_complete(self, letter: str) -> int:
        """
        Scrape a single letter completely by following pagination until the end
        """
        self.logger.info(f"Starting complete scrape for letter: {letter}")
        
        current_url = f"{self.base_url}/{letter}"
        page_count = 0
        added_count = 0
        max_pages = 50  # Safety limit
        
        while current_url and page_count < max_pages:
            page_count += 1
            self.logger.info(f"Letter {letter} - Page {page_count}: {current_url}")
            
            response = self.request_with_retry(current_url)
            if not response:
                self.logger.warning(f"Failed to fetch page {page_count} for letter {letter}")
                break
            
            # Extract nicknames using multiple strategies
            page_nicknames = self.extract_nicknames_multiple_strategies(response.text, current_url)
            
            if page_nicknames:
                old_count = len(self.player_nicknames)
                self.player_nicknames.update(page_nicknames)
                new_count = len(self.player_nicknames)
                page_added = new_count - old_count
                added_count += page_added
                
                self.logger.info(f"Letter {letter} page {page_count}: Found {len(page_nicknames)} nicknames, added {page_added} new ones")
                
                if page_added == 0 and page_count > 3:
                    # If we're not adding new nicknames and we've processed a few pages, probably reached the end
                    self.logger.info(f"No new nicknames found for letter {letter}, stopping pagination")
                    break
                
                # Find next page
                soup = BeautifulSoup(response.text, 'html.parser')
                next_url = self.find_next_page_url(soup, current_url)
                
                if next_url:
                    current_url = next_url
                    time.sleep(1.5)  # Rate limiting
                else:
                    self.logger.info(f"No next page found for letter {letter}")
                    break
            else:
                self.logger.warning(f"No nicknames found on page {page_count} for letter {letter}")
                # Try one more page before giving up
                soup = BeautifulSoup(response.text, 'html.parser')
                next_url = self.find_next_page_url(soup, current_url)
                if next_url and page_count < 3:  # Only continue if we're early in pagination
                    current_url = next_url
                    time.sleep(1.5)
                else:
                    break
        
        self.logger.info(f"Letter {letter} complete: {page_count} pages processed, {added_count} nicknames added")
        return added_count

    def scrape_all_players_smart(self) -> List[str]:
        """
        Smart scraping strategy that processes each letter completely
        """
        self.logger.info("Starting smart HLTV player scraping...")
        
        total_added = 0
        letters_processed = 0
        
        # Process each letter A-Z
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            try:
                letters_processed += 1
                self.logger.info(f"Processing letter {letter} ({letters_processed}/26)")
                
                added = self.scrape_single_letter_complete(letter)
                total_added += added
                
                self.logger.info(f"Letter {letter} completed. Total unique nicknames so far: {len(self.player_nicknames)}")
                
                # Brief pause between letters
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error processing letter {letter}: {e}")
                continue
        
        # Convert to sorted list
        sorted_nicknames = sorted(list(self.player_nicknames))
        
        self.logger.info(f"Smart scraping completed!")
        self.logger.info(f"Letters processed: {letters_processed}/26")
        self.logger.info(f"Total unique nicknames: {len(sorted_nicknames)}")
        
        return sorted_nicknames

    def save_to_files(self, player_nicknames: List[str]) -> None:
        """Save results to files"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # JSON format
        json_data = {
            'title': 'HLTV Player Nicknames (Smart Scraper)',
            'source_url': self.base_url,
            'total_count': len(player_nicknames),
            'timestamp': timestamp,
            'scraping_method': 'smart_multi_strategy',
            'player_nicknames': player_nicknames
        }
        
        with open('hltv_players_smart.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # Text format
        with open('hltv_players_smart.txt', 'w', encoding='utf-8') as f:
            f.write(f"HLTV Players (Smart Scraper)\n")
            f.write(f"{'='*50}\n")
            f.write(f"Total: {len(player_nicknames)} players\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"{'='*50}\n\n")
            
            for i, nickname in enumerate(player_nicknames, 1):
                f.write(f"{i:4d}. {nickname}\n")
        
        # CSV format
        with open('hltv_players_smart.csv', 'w', encoding='utf-8') as f:
            f.write("Number,Player Nickname\n")
            for i, nickname in enumerate(player_nicknames, 1):
                f.write(f"{i},{nickname}\n")
        
        self.logger.info("Files saved: hltv_players_smart.json, .txt, .csv")


def main():
    """Main function"""
    print("Smart HLTV Player Scraper")
    print("=" * 50)
    print("Handles pagination issues with multiple extraction strategies")
    print("=" * 50)
    
    scraper = SmartHLTVScraper()
    
    try:
        start_time = time.time()
        player_nicknames = scraper.scrape_all_players_smart()
        end_time = time.time()
        
        if not player_nicknames:
            print("Failed to get any player nicknames")
            return 1
        
        # Results
        print(f"\n{'='*60}")
        print(f"Smart Scraping Results")
        print(f"{'='*60}")
        print(f"Total time: {end_time - start_time:.2f} seconds")
        print(f"Total nicknames: {len(player_nicknames):,}")
        print(f"First 10: {player_nicknames[:10]}")
        print(f"Last 10: {player_nicknames[-10:]}")
        
        # Letter distribution
        letter_dist = {}
        for nickname in player_nicknames:
            first_letter = nickname[0].upper() if nickname else '?'
            letter_dist[first_letter] = letter_dist.get(first_letter, 0) + 1
        
        print(f"\nDistribution by letter:")
        for letter in sorted(letter_dist.keys()):
            count = letter_dist[letter]
            print(f"  {letter}: {count:,}")
        
        # Save files
        scraper.save_to_files(player_nicknames)
        print(f"\nScraping completed successfully!")
        
    except KeyboardInterrupt:
        print("\nUser interrupted")
        return 1
    except Exception as e:
        logging.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())