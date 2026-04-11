import hashlib
import base64
import re
import random
from typing import List, Dict, Any, Optional
from loguru import logger
from playwright.sync_api import Page, Locator

from ...models.schema import CrawledItem, AuthorInfo, MediaResource, DataStats, MediaType
from ...utils.parser import parse_relative_time, parse_metric_text
from ...core.base_scraper import BaseScraper

class NewsScraper(BaseScraper):
    def __init__(self, page: Page):
        super().__init__(page)

    def scrape(self, include_details: bool = False, max_items: int = 5) -> List[CrawledItem]:
        """
        Scrape the "Today's News" sidebar on the home page.
        If include_details is True, clicks into each news item to get more info and related tweets.
        """
        logger.info(f"Scraping 'Today's News' (include_details={include_details})...")
        results = []

        try:
            # Scroll back to top so the sticky sidebar news items are in the viewport
            self.page.evaluate("window.scrollTo(0, 0)")
            self.page.wait_for_timeout(800)

            # 1. Wait for news sidebar to load
            self.page.wait_for_selector('[data-testid="news_sidebar"]', timeout=15000)

            # 2. Get sidebar items
            news_locators = self.page.locator('[data-testid^="news_sidebar_article_"]').all()
            logger.info(f"Found {len(news_locators)} news items in sidebar.")

            # Limit items to process
            news_locators = news_locators[:max_items]

            for i in range(len(news_locators)):
                # Re-locate elements because DOM might refresh after navigation
                current_items = self.page.locator('[data-testid^="news_sidebar_article_"]').all()
                if i >= len(current_items):
                    break

                article = current_items[i]
                item = self._extract_news_article_data(article)
                if not item:
                    continue

                if not include_details:
                    item.source = "today_news_sidebar"
                    results.append(item)
                    continue

                # 3. Deep Scrape: Click into the news item
                try:
                    # Scroll back to top before each click so the sidebar stays in viewport
                    self.page.evaluate("window.scrollTo(0, 0)")
                    self.page.wait_for_timeout(500)
                    logger.info(f"Clicking into news: {item.title[:30]}...")
                    article.click()
                    self.page.wait_for_timeout(random.randint(3000, 5000))
                    
                    # Wait for detail container or tweets
                    # The detail container often has r-kzbkwu r-3pj75a classes
                    detail_selector = 'div.css-175oi2r.r-kzbkwu.r-3pj75a'
                    self.page.wait_for_selector(f'{detail_selector}, article[data-testid="tweet"]', timeout=15000)
                    
                    # Update news item with more details if available
                    detail_container = self.page.locator(detail_selector).first
                    if detail_container.count() > 0:
                        detail_info = self._extract_news_detail_header(detail_container)
                        if detail_info:
                            # Use the Grok summary as the main content
                            item.content = detail_info.get("summary", item.content)
                            item.publish_time = detail_info.get("publish_time") or item.publish_time
                    
                    item.source = "today_news_detail"
                    results.append(item)
                    
                    # 4. Scrape related tweets on this page
                    logger.info("Scraping related tweets for this news...")
                    related_tweets = self._scrape_related_tweets()
                    for tweet in related_tweets:
                        tweet.source = f"news_related:{item.id}"
                        results.append(tweet)
                    
                    # 5. Go back to main news page and reset scroll position
                    self.page.go_back()
                    self.page.wait_for_selector('[data-testid="news_sidebar"]', timeout=15000)
                    self.page.evaluate("window.scrollTo(0, 0)")
                    self.page.wait_for_timeout(random.randint(1000, 2000))
                    
                except Exception as e:
                    logger.warning(f"Error deep scraping news '{item.title}': {e}")
                    # If stuck, try to go home
                    if "home" not in self.page.url:
                        self.page.goto("https://x.com/home")
                        self.page.wait_for_selector('[data-testid="news_sidebar"]', timeout=15000)

        except Exception as e:
            logger.error(f"Error scraping Today's News: {e}")

        logger.info(f"Total items collected: {len(results)}")
        return results

    def _extract_news_article_data(self, article: Locator) -> Optional[CrawledItem]:
        """Extract basic sidebar data."""
        try:
            testid = article.get_attribute("data-testid") or ""
            article_id = ""
            article_link = ""

            if testid.startswith("news_sidebar_article_"):
                encoded_part = testid.replace("news_sidebar_article_", "")
                try:
                    decoded_bytes = base64.b64decode(encoded_part)
                    decoded_str = decoded_bytes.decode('utf-8')
                    match = re.search(r':(\d+)$', decoded_str)
                    if match:
                        article_id = match.group(1)
                        article_link = f"https://x.com/i/trending/{article_id}"
                except Exception: pass

            title = ""
            title_el = article.locator('span.css-1jxf684').first
            if title_el.count() > 0:
                title = title_el.inner_text()

            metadata = ""
            meta_el = article.locator('div[style*="color: rgb(113, 118, 123)"]').first
            if meta_el.count() > 0:
                metadata = meta_el.inner_text()

            post_count = 0
            if metadata:
                post_match = re.search(r'([\d.]+[KMB]?)\s+posts', metadata)
                if post_match:
                    post_count = parse_metric_text(post_match.group(1))

            if not article_id:
                article_id = hashlib.md5(title.encode()).hexdigest()[:16]
            
            return CrawledItem(
                id=article_id,
                url=article_link or f"https://x.com/search?q={title}",
                title=title,
                content=title,
                description=metadata,
                author=AuthorInfo(nickname="Today's News", username="todays_news"),
                stats=DataStats(comments=post_count),
                source="today_news"
            )
        except Exception:
            return None

    def _extract_news_detail_header(self, container: Locator) -> Dict[str, Any]:
        """Extract summary and timestamp from the news detail page header."""
        data = {}
        try:
            # Summary is usually the larger block of text in the container
            # Based on HTML: r-rjixqe r-16dba41 for the summary span
            summary_el = container.locator('span.css-1jxf684.r-poiln3').all()
            # Often there are multiple spans, the one with description is longer
            texts = [el.inner_text() for el in summary_el]
            if texts:
                # Find the longest text block which is usually the summary
                data["summary"] = max(texts, key=len)
            
            # Timestamp
            time_el = container.locator('time').first
            if time_el.count() > 0:
                data["publish_time"] = parse_relative_time(time_el.get_attribute("datetime") or "")
                
        except Exception as e:
            logger.debug(f"Error extracting news detail header: {e}")
        return data

    def _scrape_related_tweets(self) -> List[CrawledItem]:
        """Scrape related tweets from the news detail page."""
        tweets_data = []
        seen_ids = set()
        
        # Scrape a few scrolls
        for _ in range(3):
            try:
                self.page.wait_for_selector('article[data-testid="tweet"]', timeout=5000)
                tweets = self.page.locator('article[data-testid="tweet"]').all()
                
                for tweet in tweets:
                    try:
                        item = self._extract_tweet_data(tweet)
                        if item and item.id not in seen_ids:
                            tweets_data.append(item)
                            seen_ids.add(item.id)
                    except Exception: continue
                
                # Scroll
                self.page.mouse.wheel(0, random.randint(800, 1200))
                self.page.wait_for_timeout(random.randint(1500, 2500))
            except Exception: break
            
        return tweets_data

    def _extract_tweet_data(self, tweet: Locator) -> Optional[CrawledItem]:
        """Standard tweet extraction (similar to TimelineScraper)."""
        try:
            # Content
            content_el = tweet.locator('[data-testid="tweetText"]').first
            content = content_el.inner_text() if content_el.count() > 0 else ""
            
            # User
            user_el = tweet.locator('[data-testid="User-Name"]').first
            user_text = user_el.inner_text()
            parts = user_text.split('\n')
            nickname = parts[0] if parts else "Unknown"
            username = next((p for p in parts if p.startswith('@')), "@unknown").lstrip('@')
            
            # Link/Time/ID
            time_el = tweet.locator('time').first
            dt_str = time_el.get_attribute('datetime') if time_el.count() > 0 else ""
            
            link_el = tweet.locator('a[href*="/status/"]').first
            tweet_link = ""
            tweet_id = ""
            if link_el.count() > 0:
                href = link_el.get_attribute('href')
                tweet_link = f"https://x.com{href}"
                tweet_id = href.split('/')[-1]
            
            if not tweet_id:
                tweet_id = hashlib.md5(content.encode()).hexdigest()[:16]

            # Metrics
            def get_m(tid):
                el = tweet.locator(f'[data-testid="{tid}"]').first
                if el.count() > 0:
                    txt = el.inner_text()
                    if txt: return parse_metric_text(txt)
                return 0

            return CrawledItem(
                id=tweet_id,
                url=tweet_link,
                content=content,
                author=AuthorInfo(nickname=nickname, username=username),
                stats=DataStats(
                    likes=get_m("like"),
                    comments=get_m("reply"),
                    shares=get_m("retweet")
                ),
                publish_time=parse_relative_time(dt_str),
                source="news_related"
            )
        except Exception:
            return None
