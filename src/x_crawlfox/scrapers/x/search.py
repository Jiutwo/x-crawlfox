import random
import re
from typing import List
from playwright.sync_api import Page, expect
from loguru import logger

from ...core.base_scraper import BaseScraper
from ...models.schema import CrawledItem, AuthorInfo, DataStats
from ...utils.parser import parse_relative_time, parse_metric_text

class SearchScraper(BaseScraper):
    def __init__(self, page: Page, max_items: int = 20):
        super().__init__(page)
        self.max_items = max_items
        self.items = []
        self.scraped_ids = set()

    def scrape(self, keyword: str) -> List[CrawledItem]:
        logger.info(f"正在通过 Camoufox 模拟输入搜索: {keyword}")
        
        try:
            # 1. 导航到探索页（通常搜索框最明显的地方）
            self.page.goto("https://x.com/explore", wait_until="domcontentloaded")
            self.page.wait_for_timeout(random.randint(2000, 4000))
            
            # 2. 查找搜索框并模拟输入
            # X 的搜索框通常带有 data-testid="SearchBox_Search_Input"
            search_input = self.page.locator('[data-testid="SearchBox_Search_Input"]')
            
            # 如果在探索页没找到，可能在首页侧边栏
            if not search_input.is_visible():
                search_input = self.page.get_by_placeholder("Search", exact=False)
            
            if search_input.is_visible():
                search_input.click()
                # 拟人化输入
                self.page.keyboard.type(keyword, delay=random.randint(50, 150))
                self.page.wait_for_timeout(500)
                self.page.keyboard.press("Enter")
                logger.info("已模拟输入并按下回车...")
            else:
                # 兜底：如果实在找不到框，回退到直链，但这种情况很少见
                logger.warning("未能找到搜索框，回退到直链跳转...")
                self.page.goto(f"https://x.com/search?q={keyword}&src=typed_query&f=live")

            # 3. 等待结果加载并切换到 "Latest" (最新) 标签以获取实时内容
            self.page.wait_for_timeout(3000)
            latest_tab = self.page.get_by_role("link", name="Latest")
            if latest_tab.is_visible():
                latest_tab.click()
                self.page.wait_for_timeout(2000)

            # 等待第一条推文加载完毕
            self.page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
            
        except Exception as e:
            logger.error(f"模拟搜索交互失败: {e}")
            # 最后的尝试：直接跳转
            self.page.goto(f"https://x.com/search?q={keyword}&f=live")
            self.page.wait_for_timeout(5000)

        scroll_count = 0
        while len(self.items) < self.max_items and scroll_count < 30:
            tweets = self.page.locator('article[data-testid="tweet"]').all()
            
            if not tweets:
                if not self._check_and_retry_error():
                    logger.error("搜索页面持续异常且无法恢复，停止当前关键词爬取。")
                    break
                
                # 如果恢复成功，重试一轮
                self.page.mouse.wheel(0, 500)
                self.page.wait_for_timeout(2000)
                scroll_count += 1
                continue

            for tweet in tweets:
                if len(self.items) >= self.max_items:
                    break
                
                if not tweet.is_visible():
                    continue

                item = self._parse_tweet(tweet)
                if item and item.id not in self.scraped_ids:
                    self.items.append(item)
                    self.scraped_ids.add(item.id)
                    logger.info(f"已抓取: [{item.author.username}] {item.content[:20]}...")

            # 拟人化滚动
            distance = random.randint(700, 1200)
            self.page.mouse.wheel(0, distance)
            self.page.wait_for_timeout(random.randint(2000, 4000))
            scroll_count += 1
                
        return self.items

    def _parse_tweet(self, tweet_locator) -> CrawledItem:
        try:
            # 1. 解析用户信息
            user_name_elem = tweet_locator.locator('[data-testid="User-Name"]')
            full_user_text = user_name_elem.inner_text()
            
            parts = full_user_text.split('\n')
            nickname = parts[0] if parts else ""
            username = next((p for p in parts if p.startswith('@')), "")
            
            # 2. 解析正文
            content_elem = tweet_locator.locator('[data-testid="tweetText"]')
            content = content_elem.inner_text() if content_elem.count() > 0 else ""
            
            # 3. 解析时间
            time_elem = tweet_locator.locator('time')
            dt_str = time_elem.get_attribute('datetime') if time_elem.count() > 0 else None
            
            # 4. 获取推文 ID
            url_elems = tweet_locator.locator("a[href*='/status/']").all()
            tweet_path = ""
            for url_elem in url_elems:
                href = url_elem.get_attribute("href")
                if href and "/status/" in href and "photo" not in href and "video" not in href:
                    tweet_path = href
                    break

            # 5. 获取互动统计
            metrics = self._get_metrics(tweet_locator)

            return CrawledItem(
                id=tweet_path.split('/')[-1] if tweet_path else f"unknown_{random.randint(1000,9999)}",
                platform="x",
                url=f"https://x.com{tweet_path}" if tweet_path else "",
                content=content,
                author=AuthorInfo(
                    nickname=nickname,
                    username=username,
                    profile_url=f"https://x.com/{username.lstrip('@')}" if username else ""
                ),
                stats=DataStats(
                    comments=parse_metric_text(metrics.get("reply", "0")),
                    shares=parse_metric_text(metrics.get("retweet", "0")),
                    likes=parse_metric_text(metrics.get("like", "0")),
                    views=parse_metric_text(metrics.get("views", "0"))
                ),
                publish_time=parse_relative_time(dt_str) if dt_str else None,
                source="search_simulated",
                raw_data={"metrics": metrics}
            )
        except Exception as e:
            logger.debug(f"解析推文节点失败: {e}")
            return None

    def _get_metrics(self, tweet_locator):
        metrics = {"reply": "0", "retweet": "0", "like": "0", "views": "0"}
        
        # 尝试通过 aria-label 解析（通常最准）
        group_elem = tweet_locator.locator('[role="group"]').first
        if group_elem.count() > 0 and group_elem.is_visible():
            aria_label = group_elem.get_attribute('aria-label')
            if aria_label:
                reply_match = re.search(r'([\d,]+)\s+replies', aria_label, re.IGNORECASE)
                rt_match = re.search(r'([\d,]+)\s+reposts', aria_label, re.IGNORECASE)
                like_match = re.search(r'([\d,]+)\s+likes', aria_label, re.IGNORECASE)
                view_match = re.search(r'([\d,]+)\s+views', aria_label, re.IGNORECASE)
                
                if reply_match: metrics["reply"] = reply_match.group(1).replace(',', '')
                if rt_match: metrics["retweet"] = rt_match.group(1).replace(',', '')
                if like_match: metrics["like"] = like_match.group(1).replace(',', '')
                if view_match: metrics["views"] = view_match.group(1).replace(',', '')
                
                return metrics

        # 备选方案：通过 testid 查找
        for action in ["reply", "retweet", "like"]:
            elem = tweet_locator.locator(f'[data-testid="{action}"]')
            if elem.count() > 0:
                metrics[action] = elem.first.inner_text()
                
        analytics = tweet_locator.locator('a[href*="/analytics"]')
        if analytics.count() > 0:
            metrics["views"] = analytics.first.inner_text()
            
        return metrics
