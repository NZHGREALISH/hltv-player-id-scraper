# HLTV Player Nickname Scraper (A-Z Alphabetical Order)

Professional Python web scraper for extracting all player nicknames from HLTV.org in alphabetical order.

## Scraping Strategy

From **https://www.hltv.org/players/A** to **https://www.hltv.org/players/Z**, traverse in alphabetical order:
- Cover all 26 letters (A, B, C, ..., Z)
- Automatically detect pagination count for each letter page
- Ensure the most complete player data collection

## Features

- Systematic scraping in alphabetical order (A-Z)
- Automatic detection of maximum page count for each letter
- Precise extraction of player nicknames (`.players-archive-nickname.text-ellipsis`)
- Automatic deduplication and sorted output
- Network request interval control to avoid blocking
- Exception handling and retry mechanism
- Detailed logging and progress tracking
- Multiple output formats (JSON, TXT, CSV)
- First letter distribution statistics

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

## Output Files

After completion, the following files will be generated:

1. `hltv_player_nicknames.json` - JSON format with complete metadata
2. `hltv_player_nicknames.txt` - Text format for easy viewing
3. `hltv_player_nicknames.csv` - CSV format with player nicknames
4. `hltv_scraper.log` - Detailed execution log

## Technical Implementation

- **HTTP Library**: requests + Session for connection persistence
- **HTML Parsing**: BeautifulSoup4 + lxml
- **CSS Selector**: Extract player nicknames (`.players-archive-nickname.text-ellipsis`)
- **Traversal Strategy**: A-Z alphabetical order + automatic pagination detection
- **Retry Mechanism**: Automatic retry up to 2 times for network errors with incremental delay
- **Request Interval**: 1 second interval between requests to avoid blocking
- **Logging System**: Complete execution logging + progress tracking
- **Data Deduplication**: Automatic deduplication using Set collections

## Runtime Estimation

- Total scraping required: 26 letters × average pages (52 players per page)
- 1 second interval per page, estimated total time: 15-30 minutes
- Actual time depends on network conditions and data volume
- URL format example: `https://www.hltv.org/players/A?offset=153`

## Notes

- First run is estimated to take 15-30 minutes
- Please respect the website's robots.txt rules
- Recommended to run during off-peak hours
- Script will automatically retry on network issues
- Supports interruption (Ctrl+C), scraped data will be preserved

