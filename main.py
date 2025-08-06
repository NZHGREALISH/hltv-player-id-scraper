#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HLTV Player Nickname Scraper
Function: Scrape all player nicknames from https://www.hltv.org/players
Author: Python Web Scraping Engineer
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
from typing import Set, List
import logging
import os


class HLTVPlayerScraper:
    """HLTV Player Nickname Scraper Class"""
    
    # Number of players displayed per page on HLTV
    PLAYERS_PER_PAGE = 52
    
    def __init__(self):
        """Initialize the scraper"""
        self.base_url = "https://www.hltv.org/players"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.player_nicknames: Set[str] = set()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('hltv_scraper.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def request_with_retry(self, url: str, max_retries: int = 2) -> requests.Response:
        """
        Request function with retry mechanism
        
        Args:
            url: The URL to request
            max_retries: Maximum number of retries
            
        Returns:
            requests.Response: Response object
            
        Raises:
            requests.RequestException: Request failed
        """
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"Requesting: {url}")
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 2  # Incremental wait time
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    self.logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Final request failure: {e}")
                    raise

    def get_max_page_number_for_letter(self, letter: str) -> int:
        """
        Automatically detect the maximum page number for a specific letter using binary search approach
        
        Args:
            letter: Letter (A-Z)
            
        Returns:
            int: Maximum page number
        """
        self.logger.debug(f"Detecting maximum page number for letter {letter}...")
        
        try:
            # Start with the first page to check if letter has any players
            url = f"{self.base_url}/{letter}"
            response = self.request_with_retry(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if first page has any players
            nickname_elements = soup.select('.players-archive-nickname.text-ellipsis')
            if not nickname_elements:
                # No players for this letter
                self.logger.debug(f"Letter {letter} - no players found")
                return 0
            
            # Use progressive search to find the actual last page
            # Start with a reasonable upper bound and narrow down
            max_page = 1
            page_to_test = 1
            
            # First, try to find the upper bound by testing progressively larger page numbers
            test_increments = [1, 5, 10, 20, 50, 100]  # Progressive search increments
            
            for increment in test_increments:
                while True:
                    test_page = page_to_test + increment
                    test_offset = (test_page - 1) * self.PLAYERS_PER_PAGE
                    test_url = f"{self.base_url}/{letter}?offset={test_offset}"
                    
                    try:
                        self.logger.debug(f"Testing page {test_page} for letter {letter} (offset: {test_offset})")
                        test_response = self.request_with_retry(test_url)
                        test_soup = BeautifulSoup(test_response.content, 'html.parser')
                        test_nicknames = test_soup.select('.players-archive-nickname.text-ellipsis')
                        
                        if test_nicknames:
                            # This page has players, update max_page and continue
                            max_page = test_page
                            page_to_test = test_page
                            self.logger.debug(f"Letter {letter} page {test_page} has {len(test_nicknames)} players")
                        else:
                            # This page is empty, we've gone too far
                            self.logger.debug(f"Letter {letter} page {test_page} is empty, stopping increment {increment}")
                            break
                        
                        # Small delay to be respectful
                        time.sleep(0.5)
                        
                    except Exception as e:
                        self.logger.warning(f"Error testing page {test_page} for letter {letter}: {e}")
                        break
                
                # If we found the boundary with this increment, no need to try larger ones
                if page_to_test == max_page:
                    break
            
            # Now do a fine-grained search around the last known good page
            # Check a few pages after max_page to make sure we didn't miss any
            for additional_page in range(max_page + 1, max_page + 6):
                test_offset = (additional_page - 1) * self.PLAYERS_PER_PAGE
                test_url = f"{self.base_url}/{letter}?offset={test_offset}"
                
                try:
                    self.logger.debug(f"Fine-grained test page {additional_page} for letter {letter}")
                    test_response = self.request_with_retry(test_url)
                    test_soup = BeautifulSoup(test_response.content, 'html.parser')
                    test_nicknames = test_soup.select('.players-archive-nickname.text-ellipsis')
                    
                    if test_nicknames:
                        max_page = additional_page
                        self.logger.debug(f"Letter {letter} extended to page {additional_page} with {len(test_nicknames)} players")
                    else:
                        # No more players found, stop searching
                        break
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.logger.warning(f"Error in fine-grained test for page {additional_page}: {e}")
                    break
            
            self.logger.info(f"Letter {letter} detected maximum pages: {max_page}")
            return max_page
            
        except Exception as e:
            self.logger.warning(f"Error detecting page count for letter {letter}: {e}")
            self.logger.debug(f"Letter {letter} using default page count: 1")
            return 1

    def extract_player_nicknames_from_page(self, page_content: str) -> List[str]:
        """
        Extract player nicknames from page content
        
        Args:
            page_content: Page HTML content
            
        Returns:
            List[str]: List of player nicknames
        """
        soup = BeautifulSoup(page_content, 'html.parser')
        
        # Find player nickname elements
        nickname_selectors = [
            '.players-archive-nickname.text-ellipsis',  # Primary selector
            '.players-archive-nickname',                 # Backup selector
            'div[class*="nickname"]',                    # Divs containing nickname
        ]
        
        nickname_elements = []
        for selector in nickname_selectors:
            elements = soup.select(selector)
            if elements:
                nickname_elements = elements
                break
        
        nicknames = []
        for element in nickname_elements:
            # Get text content from element
            nickname = element.get_text(strip=True)
            if nickname:
                nicknames.append(nickname)
        
        # Double-check: if no nicknames found, verify this is indeed an empty page
        if not nicknames:
            # Look for any indication this page should have players
            player_containers = soup.select('.players-archive')
            player_links = soup.find_all('a', href=re.compile(r'/player/\d+'))
            
            if player_containers or player_links:
                self.logger.warning("Page structure may have changed - found player containers but no nicknames")
                # Try alternative extraction methods
                for link in player_links[:52]:  # HLTV shows max 52 per page
                    # Try to extract nickname from player link text or URL
                    link_text = link.get_text(strip=True)
                    if link_text and link_text not in nicknames:
                        nicknames.append(link_text)
        
        return nicknames

    def scrape_letter_page(self, letter: str, page_num: int) -> List[str]:
        """
        Scrape player nicknames from a specific letter and page number
        
        Args:
            letter: Letter (A-Z)
            page_num: Page number
            
        Returns:
            List[str]: List of player nicknames from that page
        """
        # Build URL
        if page_num == 1:
            url = f"{self.base_url}/{letter}"
        else:
            offset = (page_num - 1) * self.PLAYERS_PER_PAGE
            url = f"{self.base_url}/{letter}?offset={offset}"
        
        self.logger.info(f"Scraping letter {letter} page {page_num}: {url}")
        
        try:
            response = self.request_with_retry(url)
            player_nicknames = self.extract_player_nicknames_from_page(response.text)
            
            self.logger.info(f"Letter {letter} page {page_num} found {len(player_nicknames)} player nicknames")
            if player_nicknames:
                self.logger.debug(f"Nickname samples: {player_nicknames[:5]}...")
            
            return player_nicknames
            
        except Exception as e:
            self.logger.error(f"Scraping letter {letter} 第 {page_num} page error occurred: {e}")
            return []

    def scrape_all_players(self) -> List[str]:
        """
        Scrape all player nicknames in alphabetical order (A-Z)
        
        Returns:
            List[str]: Sorted list of unique player nicknames
        """
        self.logger.info("Starting to scrape HLTV player nicknames in alphabetical order (A-Z)...")
        
        # Iterate through all letters A-Z
        letters = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
        total_letters = len(letters)
        
        for letter_index, letter in enumerate(letters, 1):
            self.logger.info(f"Processing letter {letter} ({letter_index}/{total_letters})")
            
            try:
                # Get maximum page number for this letter
                max_page = self.get_max_page_number_for_letter(letter)
                
                # Skip letters with no players
                if max_page == 0:
                    self.logger.info(f"Letter {letter} has no players, skipping...")
                    continue
                
                # Iterate through all pages of this letter
                for page_num in range(1, max_page + 1):
                    try:
                        page_nicknames = self.scrape_letter_page(letter, page_num)
                        
                        # Add to set for automatic deduplication
                        old_count = len(self.player_nicknames)
                        self.player_nicknames.update(page_nicknames)
                        new_count = len(self.player_nicknames)
                        
                        if new_count > old_count:
                            self.logger.info(f"Total unique nicknames: {new_count} (+{new_count - old_count})")
                        
                        # Request interval - avoid being blocked
                        self.logger.debug("Waiting 1 second...")
                        time.sleep(1)
                        
                    except Exception as e:
                        self.logger.error(f"Scraping letter {letter} 第 {page_num} page error occurred: {e}")
                        continue
                
                # Statistics after processing each letter
                current_count = len(self.player_nicknames)
                self.logger.info(f"Letter {letter} processing completed, current total: {current_count} unique nicknames")
                
            except Exception as e:
                self.logger.error(f"Error processing letter {letter}: {e}")
                continue
        
        # Convert to sorted list
        sorted_nicknames = sorted(list(self.player_nicknames))
        
        self.logger.info(f"Scraping completed! Found {len(sorted_nicknames)} unique player nicknames")
        
        if sorted_nicknames:
            self.logger.info(f"Nickname samples: {sorted_nicknames[:10]}...")
        
        return sorted_nicknames

    def save_to_files(self, player_nicknames: List[str]) -> None:
        """
        Save player nicknames to multiple file formats
        
        Args:
            player_nicknames: List of player nicknames
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 1. Save as JSON format
        json_data = {
            'title': 'HLTV Player Nicknames',
            'source_url': self.base_url,
            'total_count': len(player_nicknames),
            'timestamp': timestamp,
            'sample_nicknames': player_nicknames[:10] if player_nicknames else [],
            'player_nicknames': player_nicknames
        }
        
        json_filename = 'hltv_player_nicknames.json'
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # 2. Save as text format
        txt_filename = 'hltv_player_nicknames.txt'
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(f"HLTV Player Nicknames List\n")
            f.write(f"{'='*50}\n")
            f.write(f"Source: {self.base_url}\n")
            f.write(f"Total: {len(player_nicknames)} players\n")
            f.write(f"Generated: {timestamp}\n")
            if player_nicknames:
                f.write(f"Nickname samples: {', '.join(player_nicknames[:5])}\n")
            f.write(f"{'='*50}\n\n")
            
            for i, nickname in enumerate(player_nicknames, 1):
                f.write(f"{i:4d}. {nickname}\n")
        
        # 3. Save as CSV format
        csv_filename = 'hltv_player_nicknames.csv'
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
    print("HLTV Player Nickname Scraper (A-Z alphabetical order)")
    print("=" * 70)
    print("Target: https://www.hltv.org/players/A to https://www.hltv.org/players/Z")
    print("Will iterate through 26 letters, each letter may have multiple pages (52 players per page)")
    print("Estimated time: 15-30 minutes (depending on network conditions)")
    print("URL example: https://www.hltv.org/players/A?offset=153")
    print("=" * 70)
    
    scraper = HLTVPlayerScraper()
    
    try:
        # Scrape all player nicknames
        start_time = time.time()
        player_nicknames = scraper.scrape_all_players()
        end_time = time.time()
        
        if not player_nicknames:
            print("Failed to get any player nicknames")
            return 1
        
        # Print statistical results
        print(f"\n{'='*70}")
        print(f"HLTV Player Nickname Scraping Results (A-Z alphabetical order)")
        print(f"{'='*70}")
        print(f"Total time: {end_time - start_time:.2f} seconds")
        print(f"Total count: {len(player_nicknames):,} unique nicknames")
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
