import random
import hashlib
import re
from typing import List, Dict, Any, Optional
from loguru import logger
from playwright.sync_api import Page, Locator

from ...models.schema import CrawledItem, AuthorInfo, MediaResource, DataStats, MediaType
from ...utils.parser import parse_relative_time, parse_metric_text
from ...core.browser import get_random_delay
from ...core.base_scraper import BaseScraper

class TimelineScraper(BaseScraper):
    def __init__(self, page: Page, max_scrolls: int = 5):
        super().__init__(page)
        self.max_scrolls = max_scrolls

    def scrape(self, tab_name: str = "Following", max_items: int = 20) -> List[CrawledItem]:
        """
        Scrape tweets from the 'For you' or 'Following' timeline.
        """
        logger.info(f"Switching to '{tab_name}' tab (max_items={max_items})...")
        try:
            self.page.wait_for_selector('div[data-testid="primaryColumn"]', timeout=20000)

            # Try English then Chinese selector
            tab = self.page.get_by_role("tab", name=tab_name)
            if not tab.is_visible():
                alt_name = "推荐" if tab_name == "For you" else "正在关注"
                tab = self.page.get_by_role("tab", name=alt_name)

            if tab.is_visible():
                tab.click()
                logger.info(f"Switched to '{tab_name}' tab")
                get_random_delay(3, 5, page=self.page)
            else:
                logger.warning(f"'{tab_name}' tab not found, attempting to scrape current view.")
        except Exception as e:
            logger.warning(f"Error switching to '{tab_name}': {e}")

        items = []
        scroll_count = 0
        seen_ids = set()

        while len(items) < max_items and scroll_count < self.max_scrolls:
            try:
                self.page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
                tweets = self.page.locator('article[data-testid="tweet"]').all()
                collected_before = len(items)

                for tweet in tweets:
                    if len(items) >= max_items:
                        break
                    try:
                        data = self._extract_tweet_data(tweet)
                        if data and data.id not in seen_ids:
                            data.source = tab_name
                            items.append(data)
                            seen_ids.add(data.id)
                    except Exception as e:
                        logger.debug(f"Error extracting tweet: {e}")
                        continue

                logger.info(f"[{tab_name}] Scroll {scroll_count + 1}/{self.max_scrolls}: {len(tweets)} in view, +{len(items) - collected_before} new, total collected: {len(items)}")

                if len(items) >= max_items:
                    break

                # Scroll logic
                scroll_y = random.randint(700, 1000)
                self.page.mouse.wheel(0, scroll_y)
                get_random_delay(2, 4, page=self.page)
                scroll_count += 1

            except Exception as e:
                if not self._check_and_retry_error():
                    logger.error(f"Error during scrolling/scraping {tab_name}: {e}")
                    break

        return items

    def _extract_tweet_data(self, tweet: Locator) -> Optional[CrawledItem]:
        """Helper to extract data from a single tweet element."""
        # 1. Text Content
        text_elements = tweet.locator('div[data-testid="tweetText"]').all()
        main_content = ""
        if len(text_elements) > 0:
            main_content = text_elements[0].inner_text()
        
        # 2. User Info
        user_element = tweet.locator('div[data-testid="User-Name"]').first
        try:
            user_text_raw = user_element.inner_text()
            user_parts = user_text_raw.split('\n')
            nickname = user_parts[0] if len(user_parts) > 0 else "Unknown"
            username = next((part for part in user_parts if part.startswith('@')), "Unknown").replace('@', '')
        except Exception:
            nickname = "Unknown"
            username = "Unknown"

        # 3. Link & Time
        tweet_link = ""
        time_str = ""
        time_element = tweet.locator('time').first
        if time_element.count() > 0:
            time_str = time_element.get_attribute("datetime") or ""
            
        link_element = tweet.locator('a[href*="/status/"]').first
        if link_element.count() > 0:
            href = link_element.get_attribute("href")
            if href:
                tweet_link = f"https://x.com{href}" if href.startswith('/') else href

        # Generate ID
        tweet_id = ""
        if tweet_link:
            parts = tweet_link.split('/')
            if 'status' in parts:
                tweet_id = parts[parts.index('status') + 1]
        
        if not tweet_id:
            tweet_id = hashlib.md5(f"{username}_{main_content[:20]}".encode()).hexdigest()[:16]

        # 4. Media
        media_list = []
        photos = tweet.locator('div[data-testid="tweetPhoto"] img').all()
        for photo in photos:
            src = photo.get_attribute("src")
            if src:
                media_list.append(MediaResource(type=MediaType.IMAGE, url=src))
                    
        video_players = tweet.locator('div[data-testid="videoPlayer"]').all()
        for player in video_players:
            video_tag = player.locator('video').first
            if video_tag.count() > 0:
                src = video_tag.get_attribute("src")
                poster = video_tag.get_attribute("poster")
                media_list.append(MediaResource(
                    type=MediaType.VIDEO,
                    url=src if src else "blob_link",
                    cover_url=poster
                ))

        # 5. Metrics
        def get_metric(testid_list):
            for testid in testid_list:
                el = tweet.locator(f'[data-testid="{testid}"]').first
                if el.count() > 0:
                    aria = el.get_attribute("aria-label") or el.locator('[aria-label]').first.get_attribute("aria-label")
                    if aria:
                        match = re.search(r'(\d[\d,.]*[KMB]?)', aria)
                        if match:
                            return parse_metric_text(match.group(1))
                    text = el.inner_text()
                    if text and any(char.isdigit() for char in text):
                        return parse_metric_text(text)
            return 0

        import re
        stats = DataStats(
            likes=get_metric(["like", "unlike"]),
            comments=get_metric(["reply"]),
            shares=get_metric(["retweet", "unretweet"]),
            collects=get_metric(["bookmark", "removeBookmark"]),
            views=0 # Simplified
        )

        return CrawledItem(
            id=tweet_id,
            url=tweet_link,
            content=main_content,
            author=AuthorInfo(nickname=nickname, username=username),
            media=media_list,
            stats=stats,
            publish_time=parse_relative_time(time_str),
            source="timeline"
        )
