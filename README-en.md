# X-CrawlFox 🦊

A human-like X (Twitter) scraping CLI tool based on Camoufox (Playwright enhanced version).

**Features**: Free, highly customizable, incremental crawling, and built-in human-like anti-bot protections.

---

## 🚀 Key Features

- **Human-like Interaction**: Integrates Camoufox fingerprint obfuscation to simulate real human scrolling, random delays, and typing interactions, significantly reducing risk of detection.
- **Timeline Scraping**: Supports crawling "Following" and "For you" feeds with configurable item limits.
- **Deep News Scraping**: Automatically scrapes the "Today's News" sidebar, with support for clicking into items to extract Grok summaries and related popular posts.
- **Incremental Account Monitoring**: Supports multi-account monitoring with automatic tracking of the last crawled tweet ID to only fetch new content.
- **All-in-One Bulk Tasks**: Launch complex scraping tasks (Timeline, News, Monitoring) via a single JSON configuration file.
- **Automatic State Management**: Automatically manages login sessions (Storage State) and crawling progress (Crawler State).

---

## 📂 Storage & Configuration (.x-crawlfox)

To protect privacy and support persistence, X-CrawlFox uses a `.x-crawlfox` directory to store sensitive data (Login Session and Crawling Progress):

1. **Path Resolution Priority**:
   - **Local Mode**: The tool first checks if a `.x-crawlfox` directory exists in the current working directory. If found, it uses this local path (ideal for isolating multiple accounts).
   - **Global Mode**: If no local directory exists, it defaults to `~/.x-crawlfox` in your home directory (Windows: `%USERPROFILE%\.x-crawlfox`).

2. **Stored Content**:
   - `storage_state.json`: Stores X login cookies and auth tokens. **Do not share this file.**
   - `crawler_state.json`: Stores the last tweet ID seen for each monitored account to enable incremental fetching.

---

## ⚙️ Installation & Setup

This project uses `uv` for package management.

1. **Clone the repository and install dependencies**:
   ```bash
   git clone <repository-url>
   cd x-crawlfox
   uv sync
   ```

2. **Install browser drivers (automatically downloaded on first run)**:
   ```bash
   uv run playwright install firefox
   ```

---

## 🛠️ Usage Guide

### 1. Account Login or Cookie Export (Required)
Before scraping, you must complete a manual login to save your session:
```bash
uv run x-crawlfox x login --no-headless
```
Log in to X in the browser window, then return to the terminal and press Enter to save the state.

**Note**: Using a newly registered account for scraping is risky and may lead to a ban.

If login is blocked by X (suspicious login detection), you can use the **Cookie Editor** browser extension to export your cookies as JSON and save them to `storage_state.json` inside your `.x-crawlfox` directory.

### 2. Scrape Personal Timeline
```bash
# Scrape the first 20 items from Following
uv run x-crawlfox x timeline --type Following --max-items 20

# Scrape the For You feed
uv run x-crawlfox x timeline --type "For you" --max-items 50
```

### 3. Scrape Today's News
```bash
# Scrape the sidebar list only
uv run x-crawlfox x news

# Deep scraping: Enter details to get summaries and related posts
uv run x-crawlfox x news --detail --max-items 3
```

### 4. Scrape/Monitor Specific User
```bash
# Fetch the latest 20 tweets from a user
uv run x-crawlfox x user elonmusk --max-tweets 20

# Incremental fetch: Only get new content since the last run
uv run x-crawlfox x user elonmusk --only-new
```

### 5. All-in-One Task
Edit `crawl_config.json` (see example below), then run:
```bash
uv run x-crawlfox x all --config crawl_config.json
```

---

## ⚙️ Configuration Example (`crawl_config.json`)

```json
{
    "timeline": [
        { "type": "Following", "max_items": 10 },
        { "type": "For you", "max_items": 10 }
    ],
    "news": {
        "enabled": true,
        "detail": true,
        "max_items": 5
    },
    "monitor": [
        { "username": "elonmusk", "only_new": true, "max_tweets": 10 },
        { "username": "OpenAI", "only_new": true, "max_tweets": 5 }
    ]
}
```

---

## 🛡️ Anti-Bot & Robustness Optimizations

- **Memory Release**: Automatically navigates to `about:blank` between account monitoring tasks to release X's massive React memory heap, preventing crashes during long runs.
- **Auto-Recovery**: If a `Target page closed` error or page crash is detected, the system attempts to rebuild the page or clicks the `Retry` button automatically.
- **Async Waiting**: Fully utilizes Playwright's non-blocking `wait_for_timeout` for better stability.
- **Randomized Behavior**: Built-in randomized scroll distances, pause durations, and human-like mouse movements.

---

## 📁 Data Output
All results are saved in `.jsonl` format in the `output/` directory, ready for data analysis or database import.

---

## 🙏 Acknowledgements

This project integrates and references these excellent open-source projects:

- [Camoufox](https://github.com/daijro/camoufox): Powerful browser fingerprint obfuscation and human-like interaction.
- [Playwright](https://playwright.dev/): Fast and robust automation and scraping framework.
- [uv](https://github.com/astral-sh/uv): Extremely efficient Python package manager.
- [last30days-skill](https://github.com/steipete/bird): Valuable reference for search strategies and GraphQL parsing.
- [Loguru](https://github.com/Delgan/loguru) & [Typer](https://typer.tiangolo.com/): For elegant logging and CLI interactions.

---

## ⚠️ Disclaimer
This tool is for educational and research purposes only. Please comply with the X (Twitter) Terms of Service. The developers are not responsible for any account restrictions or legal issues resulting from the use of this tool.
