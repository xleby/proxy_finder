# MTProto Proxy Scraper & Checker — Project Context

## Project Overview

This is a Python-based tool that automatically **scrapes**, **validates**, and **monitors MTProto proxies** for Telegram. It uses the official Telegram MTProto API via the **Telethon** library to connect through proxies and verify their availability.

### Key Features
- Scrapes MTProto proxy links from multiple Telegram channels
- Checks proxy availability by connecting through each one
- Saves working proxies to files (all scraped, only working, best)
- Sends notification reports to a Telegram chat
- Smart proxy reconnection: tries best proxy first, then .env proxy, then iterates working proxies
- Full logging to console and file

### Tech Stack
- **Python 3.10+**
- **Telethon 1.42+** — official Telegram MTProto client
- **python-dotenv** — environment variable management

---

## Directory Structure

```
telegram-proxy-checker/
├── main.py                    # Main script — scraper & checker
├── bot_send_message.py        # Standalone bot sender (sends test messages via proxy)
├── detect_chat_id.py          # Utility to detect your Telegram Chat ID
├── requirements.txt           # Dependencies
├── .env.example               # Environment config template
├── .env                       # Your secrets (gitignored)
├── .gitignore
├── README.md                  # Full documentation
├── QWEN.md                    # This file — project context
│
├── scraper.log / checker.log  # Log files
├── scraped_proxies.txt        # All scraped proxy URLs
├── working_mtproto.txt        # Verified working proxies
├── best_proxy.txt             # Best proxy (URL|latency format)
│
├── *.session                  # Telethon session files (main, bot, temp_*, detect_*)
│
├── docs/                      # Additional documentation
│   ├── README_ДЛЯ_РАЗРАБОТЧИКА.md
│   ├── PROXY_TROUBLESHOOTING.md
│   ├── BOT_VIA_MTProto.md
│   └── ... (prompts, HTML docs)
│
├── legacy/                    # Old/unused scripts (archive)
│   ├── bot_checker.py
│   ├── scraper_proxies.py
│   └── ... (9 more)
│
├── tests/                     # Test/experimental scripts
│   ├── test_proxy.py
│   ├── test_proxy_pyrogram.py
│   └── ...
│
├── telethon_lib/              # Vendored Telethon source code
├── output/                    # Output directory (legacy)
└── sessions/                  # Session storage (legacy)
```

---

## Configuration (.env)

Required variables:

| Variable | Description |
|---|---|
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API Hash |
| `PHONE` | Phone number for login (+7...) |
| `BOT_TOKEN` | Bot token from BotFather (optional, for bot features) |
| `YOUR_CHAT_ID` | Chat ID for notifications |
| `DEFAULT_PROXY_HOST/PORT/SECRET` | Fallback proxy if direct connection fails |
| `MESSAGES_LIMIT` | Messages to read per channel (default: 20) |
| `CHECK_TIMEOUT` | Connection timeout in seconds (default: 15) |
| `CHANNEL_USERNAME` | Primary channel for scraping |

---

## Running the Project

### Prerequisites
```bash
pip install -r requirements.txt
```

### Commands
```bash
# Full workflow (scrape + check)
python main.py --all

# Scrape only
python main.py --scrape

# Check only (reads from scraped_proxies.txt)
python main.py --check

# Send notification with results
python main.py --all --notify

# Detect your Chat ID
python detect_chat_id.py

# Send test message from bot
python bot_send_message.py
```

---

## Key Files

| File | Purpose |
|---|---|
| `main.py` | Core script. Handles scraping, checking, saving, and notifications. Contains all business logic. |
| `bot_send_message.py` | Standalone utility to send a test message from a bot through an MTProto proxy. |
| `detect_chat_id.py` | Helper to auto-detect and write your Chat ID to `.env`. |
| `best_proxy.txt` | Stores the fastest working proxy URL and its latency (pipe-separated). |
| `scraped_proxies.txt` | All proxies found during scraping. |
| `working_mtproto.txt` | Only proxies that passed the connection check. |

---

## Architecture & Flow

1. **Connection**: Script starts by trying to connect through the best known proxy (from `best_proxy.txt`), then falls back to `.env` proxy, then iterates `working_mtproto.txt`.
2. **Scraping**: Iterates through a hardcoded list of ~10 channels, extracts proxy URLs from message text using regex patterns (`t.me/proxy?...` and `Server/Port/Secret` formats).
3. **Checking**: For each proxy, creates a temporary Telethon client, attempts connection, measures latency, and verifies auth status.
4. **Saving**: Results are written to `scraped_proxies.txt`, `working_mtproto.txt`, and `best_proxy.txt`.
5. **Notification**: Sends an HTML-formatted report with clickable proxy links to the configured chat.

---

## Coding Conventions

- **Language**: Python with Russian comments and log messages
- **Style**: Procedural, organized into sections with comment separators (`# === SECTION ===`)
- **Async**: Uses `asyncio` for all Telegram operations
- **Error handling**: Try/except blocks with logging at each level
- **No classes** — all functions are module-level

---

## Important Notes

- Session files (`.session`) should **never be committed**
- `.env` contains credentials and is **gitignored**
- The `legacy/` directory contains old scripts that have been superseded by `main.py`
- Temporary session files (`temp_*.session`) are created during proxy checks and should be cleaned up automatically
- The `telethon_lib/` directory contains vendored Telethon source (not typically needed)
