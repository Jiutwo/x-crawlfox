import json
import random
from pathlib import Path
from typing import Optional
from loguru import logger
import typer

from .config import ConfigManager
from .utils import save_items, handle_error
from ..core.browser import BrowserManager
from ..scrapers.x.timeline import TimelineScraper
from ..scrapers.x.news import NewsScraper
from ..scrapers.x.profile import ProfileScraper
from ..scrapers.x.search import SearchScraper

x_app = typer.Typer(help="X (Twitter) scraping commands")


@x_app.command()
def login(
    ctx: typer.Context,
    headless: bool = typer.Option(False, "--headless/--no-headless", help="Whether to use headless mode"),
):
    """
    Open browser for manual X login, and save login state to .x-crawlfox/x_cookies.json upon completion.
    """
    cfg: ConfigManager = ctx.obj["config"]
    try:
        logger.info("Starting browser for manual login...")
        with BrowserManager(headless=headless) as context:
            page = context.new_page()
            logger.info("Navigating to X login page...")
            page.goto("https://x.com/i/flow/login", timeout=40000)

            logger.info("-" * 50)
            logger.info("Please complete login in the popup browser window.")
            logger.info("After login is complete, return here and press Enter to save state and exit...")
            logger.info("-" * 50)
            input()

            bm = BrowserManager()
            bm.context = context
            bm.save_auth_state(path=str(cfg.auth_path))
            logger.info(f"Login state successfully saved to {cfg.auth_path}")
    except Exception as e:
        handle_error(e)


@x_app.command()
def timeline(
    type: str = typer.Option("Following", help="Scrape type: 'For you' or 'Following'"),
    max_items: int = typer.Option(20, help="Maximum number of tweets to scrape"),
    max_scrolls: int = typer.Option(5, help="Maximum number of downward scrolls"),
    output: str = typer.Option("output", "--output", "-o", help="Directory to save data"),
    headless: bool = typer.Option(True, help="Whether to use headless mode"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address (e.g. http://127.0.0.1:7890)"),
):
    """
    Scrape your personal timeline tweets.
    """
    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            logger.info(f"Preparing to scrape {type} timeline...")
            page.goto("https://x.com/home", timeout=40000)
            scraper = TimelineScraper(page, max_scrolls=max_scrolls)
            items = scraper.scrape(tab_name=type, max_items=max_items)
            if items:
                save_items(items, f"timeline_{type.lower().replace(' ', '_')}", output_dir=output)
            else:
                logger.warning("Failed to scrape any tweets. Please check if you are logged in or if the page loaded normally.")
    except Exception as e:
        handle_error(e)


@x_app.command()
def news(
    ctx: typer.Context,
    detail: bool = typer.Option(False, "--detail", help="Whether to click in and scrape news details and related posts"),
    max_items: int = typer.Option(5, help="Maximum number of news items to process"),
    output: str = typer.Option("output", "--output", "-o", help="Directory to save data"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Whether to use headless mode"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address"),
):
    """
    Scrape sidebar today's news, supports deep scraping of details and posts.
    """
    cfg: ConfigManager = ctx.obj["config"]
    try:
        with BrowserManager(auth_file=cfg.auth_path, headless=headless, proxy=proxy) as context:
            page = context.new_page()
            page.goto("https://x.com/home", timeout=60000)
            scraper = NewsScraper(page)
            items = scraper.scrape(include_details=detail, max_items=max_items)
            if items:
                suffix = "detailed" if detail else "sidebar"
                save_items(items, f"today_news_{suffix}", output_dir=output)
            else:
                logger.warning("Failed to scrape today's news.")
    except Exception as e:
        handle_error(e)


@x_app.command()
def user(
    ctx: typer.Context,
    username: str = typer.Argument(...),
    max_tweets: int = typer.Option(20, help="Maximum number of tweets to scrape"),
    only_new: bool = typer.Option(False, "--only-new", help="Whether to only scrape new content"),
    output: str = typer.Option("output", "--output", "-o", help="Directory to save data"),
    headless: bool = typer.Option(True, help="Whether to use headless mode"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address"),
):
    """
    Scrape tweets from a specified user's profile, supports incremental scraping.
    """
    cfg: ConfigManager = ctx.obj["config"]
    try:
        with BrowserManager(auth_file=cfg.auth_path, headless=headless, proxy=proxy) as context:
            page = context.new_page()
            scraper = ProfileScraper(page)
            items = scraper.scrape_user(username, only_new=only_new, max_tweets=max_tweets)
            if items:
                save_items(items, f"profile_{username}", output_dir=output)
            else:
                logger.warning(f"Failed to scrape new tweets for user @{username}.")
    except Exception as e:
        handle_error(e)


@x_app.command()
def monitor(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(None, help="Monitor config file path (JSON flat list); if unspecified, reads from .x-crawlfox/crawl_config.json's x.monitor"),
    global_max: int = typer.Option(100, help="Global maximum total tweets to scrape per monitor run"),
    output: str = typer.Option("output", "--output", "-o", help="Directory to save data"),
    headless: bool = typer.Option(True, help="Whether to use headless mode"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address"),
):
    """
    Monitor new tweets for multiple accounts.
    If --config is not specified, reads account list from x.monitor section in .x-crawlfox/crawl_config.json.
    If --config is specified, reads flat list format: [{"username": "...", "only_new": true, ...}]
    """
    cfg: ConfigManager = ctx.obj["config"]

    if config is None:
        config_path = cfg.get_crawl_config_path()
        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}. Please run 'x-crawlfox init' first or specify --config.")
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                full_config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse config file: {e}")
            return
        users_config = full_config.get("x", full_config).get("monitor", [])
        if not users_config:
            logger.error("x.monitor config not found in crawl_config.json. Please add it and try again.")
            return
    else:
        config_path = Path(config)
        if not config_path.exists():
            logger.error(f"Config file not found: {config}")
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                users_config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse config file: {e}")
            return

    try:
        with BrowserManager(auth_file=cfg.auth_path, headless=headless, proxy=proxy) as context:
            page = context.new_page()
            scraper = ProfileScraper(page)
            items = scraper.monitor_users(users_config, global_max=global_max)
            if items:
                save_items(items, "monitor_results", output_dir=output)
            else:
                logger.warning("Monitor run finished. No new tweets found.")
    except Exception as e:
        handle_error(e)


@x_app.command()
def search(
    keyword: str = typer.Argument(..., help="Search keyword"),
    max_items: int = typer.Option(20, help="Maximum number of tweets to scrape"),
    output: str = typer.Option("output", "--output", "-o", help="Directory to save data"),
    headless: bool = typer.Option(True, help="Whether to use headless mode"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address"),
):
    """
    Search and scrape tweets on X based on keywords (simulating real input mode).
    """
    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            logger.info(f"Searching via simulated interaction: {keyword}")
            scraper = SearchScraper(page, max_items=max_items)
            items = scraper.scrape(keyword)
            if items:
                save_items(items, f"search_{keyword.replace(' ', '_')}", output_dir=output)
            else:
                logger.warning(f"Failed to scrape tweets for '{keyword}'.")
    except Exception as e:
        handle_error(e)


@x_app.command()
def all(
    ctx: typer.Context,
    config: str = typer.Option(None, help="Crawl config file path. If unspecified, loads from .x-crawlfox directory"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Directory to save data (overrides global.output_dir)"),
    headless: Optional[bool] = typer.Option(None, "--headless/--no-headless", help="Whether to use headless mode (overrides global.headless)"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address"),
):
    """
    [One-click Crawl] Execute full crawl task based on config file.
    If config is specified, it takes priority, otherwise loads from .x-crawlfox directory.
    """
    config_manager: ConfigManager = ctx.obj["config"]
    config_path = Path(config) if config else config_manager.get_crawl_config_path()

    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            full_config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse config file: {e}")
        return

    global_config = full_config.get("global", {})
    effective_headless = headless if headless is not None else global_config.get("headless", True)
    effective_output = output if output is not None else global_config.get("output_dir", "output")

    x_config = full_config.get("x", full_config)
    all_items = []

    try:
        with BrowserManager(auth_file=config_manager.auth_path, headless=effective_headless, proxy=proxy) as context:
            page = context.new_page()

            # 1. Timeline
            timeline_configs = x_config.get("timeline", [])
            if timeline_configs:
                logger.info(">>> Starting timeline crawl...")
                try:
                    if page.is_closed():
                        page = context.new_page()
                    page.goto("https://x.com/home")
                    for tc in timeline_configs:
                        t_type = tc.get("type", "Following")
                        m_scrolls = tc.get("max_scrolls", 5)
                        m_items = tc.get("max_items", 20)
                        logger.info(f"Processing {t_type} timeline (max_items={m_items}, max_scrolls={m_scrolls})...")
                        scraper = TimelineScraper(page, max_scrolls=m_scrolls)
                        items = scraper.scrape(tab_name=t_type, max_items=m_items)
                        all_items.extend(items)
                        page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"Error in timeline crawling module: {e}")

            # 2. News
            news_config = x_config.get("news", {})
            if news_config.get("enabled"):
                logger.info(">>> Starting today's news crawl...")
                try:
                    if page.is_closed():
                        page = context.new_page()
                    page.goto("https://x.com/home")
                    scraper = NewsScraper(page)
                    items = scraper.scrape(
                        include_details=news_config.get("detail", False),
                        max_items=news_config.get("max_items", 5),
                    )
                    all_items.extend(items)
                    page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"Error in news crawling module: {e}")

            # 3. Monitor (Profile)
            monitor_configs = x_config.get("monitor", [])
            if monitor_configs:
                logger.info(">>> Starting account tweet monitor...")
                try:
                    if page.is_closed():
                        logger.warning("Page closed, opening new page for monitor module...")
                        page = context.new_page()
                    scraper = ProfileScraper(page)
                    items = scraper.monitor_users(monitor_configs)
                    all_items.extend(items)
                    page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"Error in account monitor module: {e}")

            # 4. Search
            search_configs = x_config.get("search", [])
            if search_configs:
                logger.info(">>> Starting keyword search...")
                try:
                    for sc in search_configs:
                        if page.is_closed():
                            logger.warning("Page closed, opening new page for search task...")
                            page = context.new_page()
                        kw = sc.get("keyword")
                        m_items = sc.get("max_items", 20)
                        if kw:
                            logger.info(f"Search keyword: {kw} (max_items={m_items})...")
                            scraper = SearchScraper(page, max_items=m_items)
                            items = scraper.scrape(kw)
                            all_items.extend(items)
                            page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"Error in keyword search module: {e}")

            if all_items:
                save_items(all_items, "all_crawled_results", output_dir=effective_output)
            else:
                logger.warning("Full crawl task finished, no data scraped.")

    except Exception as e:
        handle_error(e)
