# X-CrawlFox 🦊
[![License](https://img.shields.io/github/license/Jiutwo/x-crawlfox)](https://opensource.org/licenses/Apache-2.0) ![Python Version](https://img.shields.io/badge/python-3.10%2B-blue) [![GitHub stars](https://img.shields.io/github/stars/Jiutwo/x-crawlfox)](https://github.com/Jiutwo/x-crawlfox/stargazers)

A free, high-anonymity X (Twitter) human-like scraping CLI tool.

🌐 **English** | [中文](./README-zh.md)

---

## 🚀 Key Features
**Features**: Free, highly customizable, incremental crawling, and built-in human-like behavior for anti-bot protection.

- **Human-like Interaction**: Integrates Camoufox fingerprint obfuscation to simulate real human scrolling, random delays, and typing interactions, significantly reducing the risk of detection.
- **Timeline Scraping**: Supports crawling "Following" and "For you" feeds with configurable item limits.
- **Deep News Scraping**: Automatically scrapes the "Today's News" sidebar, with support for clicking into details to extract Grok summaries and related popular posts.
- **Keyword Search**: Simulates real keyboard input for search queries to bypass anti-bot detection.
- **Incremental Account Monitoring**: Supports multi-account monitoring with automatic tracking of the last crawled tweet ID to only fetch new content.
- **One-click Composite Tasks**: Launch composite tasks (Timeline, News, Monitoring, Search) via a unified JSON configuration file.
- **Automatic State Management**: Automatically saves login sessions (Cookie) and crawling progress (Crawler State).

---

## 📦 Quick Start

### Installation

1. **Install from PyPI**:
   ```bash
   pip install x-crawlfox
   ```

2. **Build from source**: This project uses `uv` for package management.
   ```bash
   git clone https://github.com/Jiutwo/x-crawlfox.git
   cd x-crawlfox
   uv sync
   ```

### How to Use

#### 1. Initialize Config Directory

Before first use, run the following command to generate the `.x-crawlfox` configuration folder and default settings in the current directory:

```bash
x-crawlfox init

# To save the configuration to the user home directory (Global Mode):
x-crawlfox init --global
```

#### 2. Account Login or Cookie Export (Required)

You must have a logged-in session (Cookie) before scraping.

**Note**: Scraping immediately with a newly registered account is risky; it is recommended to use the account normally for a while first.

**Method 1: Export via Cookie Editor Extension (Recommended)**

Use the browser extension **Cookie Editor** to export your current session cookies as JSON and save them to `.x-crawlfox/x_cookies.json`.

The `.x-crawlfox` folder can be located in the current directory or the user home directory. X-CrawlFox will automatically recognize and convert the Cookie Editor format to the required internal format upon loading.

![Cookie Editor](./docs/images/cookie-editor-export.jpg)

**Method 2: Command Line Login**

```bash
x-crawlfox x login
```

Complete the login in the popup browser window, then return to the terminal and press Enter to save the state. The login state will be automatically saved to `.x-crawlfox/x_cookies.json`.

> If X blocks the login as a "suspicious attempt," please switch to Method 1.

#### 3. Scrape Personal Timeline

```bash
# Scrape the first 20 items from the Following feed
# Add --no-headless to visualize the process
x-crawlfox x timeline --type Following --max-items 20

# Scrape the For You feed
x-crawlfox x timeline --type "For you" --max-items 50
```

#### 4. Scrape Today's News

```bash
# Scrape sidebar list only
x-crawlfox x news

# Deep scraping: Enter details to get summaries and related posts
x-crawlfox x news --detail --max-items 3
```

#### 5. Scrape/Monitor Specific User

```bash
# Fetch the latest 20 tweets from a specific user
x-crawlfox x user elonmusk --max-tweets 20

# Incremental fetch: Only get new content since the last run
x-crawlfox x user elonmusk --only-new
```

Run multi-account monitoring independently (reads `x.monitor` from `crawl_config.json`):

```bash
x-crawlfox x monitor
```

You can also specify a custom config file (flat list format):

```bash
x-crawlfox x monitor --config my_accounts.json
```

#### 6. One-click Composite Tasks

Edit `.x-crawlfox/crawl_config.json`, then run:

```bash
x-crawlfox x all
```

You can also specify a different config file path via `--config`:

```bash
x-crawlfox x all --config /path/to/crawl_config.json
```

Example `crawl_config.json` format:

```json
{
    "global": {
        "output_dir": "output",
        "headless": true
    },
    "x": {
        "timeline": [
            { "type": "For you",   "max_scrolls": 2, "max_items": 10 },
            { "type": "Following", "max_scrolls": 3, "max_items": 10 }
        ],
        "news": {
            "enabled": true,
            "detail": true,
            "max_items": 5
        },
        "monitor": [
            { "username": "elonmusk", "only_new": true, "max_tweets": 10 },
            { "username": "OpenAI",   "only_new": true, "max_tweets": 10 }
        ]
    }
}
```

---

### 📂 Storage & Configuration (.x-crawlfox)

To protect privacy and support persistence, X-CrawlFox uses the `.x-crawlfox` folder to store sensitive data:

1. **Storage Location**:
   - **Local Mode**: The program first checks if `.x-crawlfox` exists in the current working directory. If found, all data is stored here (ideal for account isolation).
   - **Global Mode**: If the local directory does not exist, it defaults to `~/.x-crawlfox` in the user home directory (Windows: `%USERPROFILE%\.x-crawlfox`).

2. **Stored Content**:
   - `x_cookies.json`: Stores X login cookies and auth tokens. **Do not share this file.**
   - `crawl_config.json`: Unified configuration file for the `all` and `monitor` commands.
   - `x_crawl_state.json`: Stores the last tweet ID fetched for each monitored account to enable incremental fetching.

3. **Output Location**:
   All scraping results are saved in `.jsonl` format in the `output/` directory for easy analysis or database import.

---

## 🙏 Acknowledgments

This project is deeply inspired by the open-source community and integrates excellent open-source projects such as [Camoufox](https://github.com/daijro/camoufox). Sincere thanks to all the open-source libraries and developers who provide foundational support for this project.

---

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Please comply with the X (Twitter) Terms of Service. The developers are not responsible for any account restrictions or legal issues resulting from the use of this tool.
