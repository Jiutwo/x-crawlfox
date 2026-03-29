import json
import typer
import sys
import random
from pathlib import Path
from typing import Optional, List
from loguru import logger
from datetime import datetime
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ..core.browser import BrowserManager
from ..scrapers.x.timeline import TimelineScraper
from ..scrapers.x.news import NewsScraper
from ..scrapers.x.profile import ProfileScraper
from ..scrapers.x.search import SearchScraper
from ..models.schema import CrawledItem

app = typer.Typer(help="x-crawlfox: A multi-platform web scraping CLI tool")
x_app = typer.Typer(help="X (Twitter) scraping commands")

def handle_error(e: Exception):
    """统一错误处理逻辑"""
    if isinstance(e, PlaywrightTimeoutError):
        logger.error("连接超时！请检查您的网络环境（是否需要开启 VPN）或代理设置 (--proxy)。")
        logger.debug(f"详细错误: {e}")
    elif isinstance(e, PlaywrightError):
        logger.error(f"浏览器自动化错误: {e.message}")
        if "executable" in e.message.lower():
            logger.info("提示: 请尝试运行 'playwright install' 安装所需的浏览器驱动。")
    elif isinstance(e, KeyboardInterrupt):
        logger.warning("\n用户中止了操作。")
    else:
        logger.exception(f"发生未知错误: {e}")

def save_items(items: List[CrawledItem], filename: str, output_dir: str = "output"):
    save_path_dir = Path(output_dir)
    save_path_dir.mkdir(parents=True, exist_ok=True)
    
    if not filename.endswith(".jsonl"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = save_path_dir / f"{filename}_{timestamp}.jsonl"
    else:
        filepath = save_path_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")
    
    logger.info(f"保存成功！共 {len(items)} 条数据存至 {filepath}")

# X Platform Commands
@x_app.command()
def login(headless: bool = typer.Option(False, "--headless/--no-headless", help="是否使用无头模式")):
    """
    打开浏览器进行手动登录并保存登录状态。
    """
    try:
        logger.info("正在启动浏览器以进行手动登录...")
        with BrowserManager(headless=headless) as context:
            page = context.new_page()
            logger.info("正在导航至 X 登录页面...")
            page.goto("https://x.com/i/flow/login", timeout=60000)
            
            logger.info("-" * 50)
            logger.info("请在弹出的浏览器窗口中完成登录。")
            logger.info("登录完成后，请回到此处按 Enter 键保存状态并退出...")
            logger.info("-" * 50)
            input()
            
            bm = BrowserManager()
            bm.context = context
            bm.save_auth_state()
            logger.info("登录状态已成功保存至 .auth/storage_state.json")
    except Exception as e:
        handle_error(e)

@x_app.command()
def timeline(
    type: str = typer.Option("Following", help="爬取类型: 'Following' 或 'For you'"),
    max_items: int = typer.Option(20, help="要爬取的最大推文数量"),
    max_scrolls: int = typer.Option(5, help="向下滚动的次数上限"),
    output: str = typer.Option("output", "--output", "-o", help="保存数据的目录"),
    headless: bool = typer.Option(True, help="是否使用无头模式"),
    proxy: Optional[str] = typer.Option(None, help="代理服务器地址 (例如 http://127.0.0.1:7890)")
):
    """
    爬取您的个人时间线推文。
    """
    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            logger.info(f"正在准备爬取 {type} 时间线...")
            page.goto("https://x.com/home", timeout=60000)
            
            scraper = TimelineScraper(page, max_scrolls=max_scrolls)
            items = scraper.scrape(tab_name=type, max_items=max_items)
            
            if items:
                save_items(items, f"timeline_{type.lower().replace(' ', '_')}", output_dir=output)
            else:
                logger.warning("未能抓取到任何推文，请检查是否已登录或页面加载是否正常。")
    except Exception as e:
        handle_error(e)

@x_app.command()
def news(
    detail: bool = typer.Option(False, "--detail", help="是否点击进入并抓取新闻详情及相关帖子"),
    max_items: int = typer.Option(5, help="最多处理的新闻条目数"),
    output: str = typer.Option("output", "--output", "-o", help="保存数据的目录"),
    headless: bool = typer.Option(True, help="是否使用无头模式"),
    proxy: Optional[str] = typer.Option(None, help="代理服务器地址")
):
    """
    爬取侧边栏的今日新闻 (Today's News)，支持深度爬取详情和帖子。
    """
    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            page.goto("https://x.com/home", timeout=60000)
            
            scraper = NewsScraper(page)
            items = scraper.scrape(include_details=detail, max_items=max_items)
            
            if items:
                suffix = "detailed" if detail else "sidebar"
                save_items(items, f"today_news_{suffix}", output_dir=output)
            else:
                logger.warning("未能抓取到今日新闻。")
    except Exception as e:
        handle_error(e)

@x_app.command()
def user(
    username: str,
    max_tweets: int = typer.Option(20, help="要爬取的最大推文数量"),
    only_new: bool = typer.Option(False, "--only-new", help="是否只爬取新内容"),
    output: str = typer.Option("output", "--output", "-o", help="保存数据的目录"),
    headless: bool = typer.Option(True, help="是否使用无头模式"),
    proxy: Optional[str] = typer.Option(None, help="代理服务器地址")
):
    """
    爬取指定用户主页的推文，支持增量爬取。
    """
    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            scraper = ProfileScraper(page)
            items = scraper.scrape_user(username, only_new=only_new, max_tweets=max_tweets)
            
            if items:
                save_items(items, f"profile_{username}", output_dir=output)
            else:
                logger.warning(f"未能抓取到用户 @{username} 的新推文。")
    except Exception as e:
        handle_error(e)

@x_app.command()
def monitor(
    config: str = typer.Option("monitor_config.json", help="监控配置文件路径 (JSON)"),
    global_max: int = typer.Option(100, help="单次监控抓取的全球最大推文总数"),
    output: str = typer.Option("output", "--output", "-o", help="保存数据的目录"),
    headless: bool = typer.Option(True, help="是否使用无头模式"),
    proxy: Optional[str] = typer.Option(None, help="代理服务器地址")
):
    """
    根据配置文件监控多个账号的新推文。
    """
    config_path = Path(config)
    if not config_path.exists():
        logger.error(f"配置文件未找到: {config}")
        return

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            users_config = json.load(f)
    except Exception as e:
        logger.error(f"解析配置文件失败: {e}")
        return

    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            scraper = ProfileScraper(page)
            items = scraper.monitor_users(users_config, global_max=global_max)
            
            if items:
                save_items(items, f"monitor_results", output_dir=output)
            else:
                logger.warning("监控运行结束，未发现新推文。")
    except Exception as e:
        handle_error(e)

@x_app.command()
def search(
    keyword: str = typer.Argument(..., help="搜索关键词"),
    max_items: int = typer.Option(20, help="要爬取的最大推文数量"),
    output: str = typer.Option("output", "--output", "-o", help="保存数据的目录"),
    headless: bool = typer.Option(True, help="是否使用无头模式"),
    proxy: Optional[str] = typer.Option(None, help="代理服务器地址")
):
    """
    基于关键字搜索并爬取 X 上的推文（模拟真实输入模式）。
    """
    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            
            logger.info(f"正在通过模拟交互搜索: {keyword}")
            scraper = SearchScraper(page, max_items=max_items)
            items = scraper.scrape(keyword)

            if items:
                save_items(items, f"search_{keyword.replace(' ', '_')}", output_dir=output)
            else:
                logger.warning(f"未能抓取到关于 '{keyword}' 的推文。")
    except Exception as e:
        handle_error(e)

@x_app.command()
def all(
    config: str = typer.Option("crawl_config.json", help="全量爬取配置文件路径 (JSON)"),
    output: str = typer.Option("output", "--output", "-o", help="保存数据的目录"),
    headless: bool = typer.Option(True, help="是否使用无头模式"),
    proxy: Optional[str] = typer.Option(None, help="代理服务器地址")
):
    """
    [一键爬取] 根据配置文件执行全量爬取任务。
    """
    config_path = Path(config)
    if not config_path.exists():
        logger.error(f"配置文件未找到: {config}")
        return

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            full_config = json.load(f)
    except Exception as e:
        logger.error(f"解析配置文件失败: {e}")
        return

    all_items = []
    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            
            # 1. Timeline
            timeline_configs = full_config.get("timeline", [])
            if timeline_configs:
                logger.info(">>> 开始爬取时间线...")
                try:
                    if page.is_closed(): page = context.new_page()
                    page.goto("https://x.com/home")
                    for tc in timeline_configs:
                        t_type = tc.get("type", "Following")
                        m_scrolls = tc.get("max_scrolls", 5)
                        m_items = tc.get("max_items", 20)
                        logger.info(f"正在处理 {t_type} 时间线 (max_items={m_items}, max_scrolls={m_scrolls})...")
                        scraper = TimelineScraper(page, max_scrolls=m_scrolls)
                        items = scraper.scrape(tab_name=t_type, max_items=m_items)
                        all_items.extend(items)
                        page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"爬取时间线模块发生错误: {e}")

            # 2. News
            news_config = full_config.get("news", {})
            if news_config.get("enabled"):
                logger.info(">>> 开始爬取今日新闻...")
                try:
                    if page.is_closed(): page = context.new_page()
                    if "home" not in page.url:
                        page.goto("https://x.com/home")
                    scraper = NewsScraper(page)
                    items = scraper.scrape(
                        include_details=news_config.get("detail", False),
                        max_items=news_config.get("max_items", 5)
                    )
                    all_items.extend(items)
                    page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"爬取新闻模块发生错误: {e}")

            # 3. Monitor (Profile)
            monitor_configs = full_config.get("monitor", [])
            if monitor_configs:
                logger.info(">>> 开始监控账号推文...")
                try:
                    if page.is_closed():
                        logger.warning("页面已关闭，正在为监控模块开启新页面...")
                        page = context.new_page()
                    scraper = ProfileScraper(page)
                    items = scraper.monitor_users(monitor_configs)
                    all_items.extend(items)
                    page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"账号监控模块发生错误: {e}")

            # 4. Search
            search_configs = full_config.get("search", [])
            if search_configs:
                logger.info(">>> 开始执行关键词搜索...")
                try:
                    for sc in search_configs:
                        if page.is_closed():
                            logger.warning("页面已关闭，正在为搜索任务开启新页面...")
                            page = context.new_page()
                        
                        kw = sc.get("keyword")
                        m_items = sc.get("max_items", 20)
                        if kw:
                            logger.info(f"搜索关键词: {kw} (max_items={m_items})...")
                            scraper = SearchScraper(page, max_items=m_items)
                            items = scraper.scrape(kw)
                            all_items.extend(items)
                            page.wait_for_timeout(random.randint(5000, 10000))
                except Exception as e:
                    logger.error(f"关键词搜索模块发生错误: {e}")

            if all_items:
                save_items(all_items, "all_crawled_results", output_dir=output)
            else:
                logger.warning("全量爬取任务结束，未抓取到任何数据。")

    except Exception as e:
        handle_error(e)

# Register Platform Apps
app.add_typer(x_app, name="x")

# Global login command (alias for x login for backward compatibility or convenience)
@app.command()
def login(headless: bool = typer.Option(False, "--headless/--no-headless", help="是否使用无头模式")):
    """
    [Alias] 打开浏览器进行 X 手动登录。
    """
    try:
        logger.info("正在启动浏览器以进行手动登录...")
        with BrowserManager(headless=headless) as context:
            page = context.new_page()
            logger.info("正在导航至 X 登录页面...")
            page.goto("https://x.com/i/flow/login", timeout=60000)
            
            logger.info("-" * 50)
            logger.info("请在弹出的浏览器窗口中完成登录。")
            logger.info("登录完成后，请回到此处按 Enter 键保存状态并退出...")
            logger.info("-" * 50)
            input()
            
            bm = BrowserManager()
            bm.context = context
            bm.save_auth_state()
            logger.info("登录状态已成功保存至 .auth/storage_state.json")
    except Exception as e:
        handle_error(e)

if __name__ == "__main__":
    app()
