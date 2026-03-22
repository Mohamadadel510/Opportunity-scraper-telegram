# Opportunity Scraper

A Python script that scrapes job opportunities, internships, scholarships, and fellowships from specified Telegram channels using AI (Groq) for filtering and categorization, then stores valid opportunities in a Notion database.

## Features

- Scrapes messages from Telegram channels
- Uses Groq AI to analyze and categorize opportunities
- Filters out duplicates and irrelevant content
- Stores structured data in Notion database
- Handles rate limiting and retries
- Persistent storage of seen messages

## Prerequisites

- Python 3.8+
- Telegram API credentials (api_id and api_hash)
- Groq API key
- Notion integration token and database ID

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Mohamadadel510/Opportunity-scraper-telegram.git
   cd Opportunity-scraper-telegram
   ```

2. Install dependencies:
   ```bash
   pip install telethon groq httpx notion-client python-dateutil
   ```

## Setup

1. **Telegram Setup:**
   - Get your `api_id` and `api_hash` from [Telegram API](https://my.telegram.org/auth)
   - Update the `api_id` and `api_hash` in the script

2. **Groq API:**
   - Sign up at [Groq Console](https://console.groq.com)
   - Get your API key

3. **Notion Setup:**
   - Create a new integration at [Notion Developers](https://developers.notion.com/)
   - Create a database with properties: Title, Description, Link, Category, Date, Channel
   - Share the database with your integration
   - Get the `DATABASE_ID` from the URL

4. **Environment Variables:**
   Set these environment variables (recommended for security):
   ```bash
   export GROQ_API_KEY="your_groq_api_key"
   export NOTION_TOKEN="your_notion_integration_token"
   ```
   Or edit the script to replace `os.getenv("GROQ_API_KEY")` with your actual key (not recommended for public repos).

## Usage

1. Set environment variables or edit the script with your keys
2. Run the script:
   ```bash
   python op_scraper.py
   ```

The script will:
- Connect to Telegram
- Scrape recent messages from target channels
- Use AI to identify opportunities
- Save new opportunities to Notion

## Configuration

- `TARGET_CHANNELS`: List of Telegram channel usernames to scrape
- `MSG_LIMIT`: Number of messages to fetch per channel
- `GROQ_DELAY`: Delay between AI API calls
- `DATABASE_ID`: Your Notion database ID

## Files

- `op_scraper.py`: Main script
- `seen_hashes.json`: Tracks processed messages
- `last_msg_ids.json`: Stores last message IDs per channel
- `session.session`: Telegram session file (generated automatically)

## Security Note

Never commit API keys to version control. Use environment variables or a secure secrets manager.

## Contributing

Feel free to submit issues and pull requests.

## License

MIT License
