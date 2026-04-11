import random
from typing import List, Optional, Dict
from loguru import logger
from playwright.sync_api import Page, Locator

from ...models.schema import CrawledItem
from .timeline import TimelineScraper
from ...core.browser import get_random_delay
from ...utils.state import StateManager

class ProfileScraper(TimelineScraper):
    def __init__(self, page: Page, max_scrolls: int = 5):
        super().__init__(page, max_scrolls)
        self.state_manager = StateManager()

    def scrape_user(self, 
                    username: str, 
                    only_new: bool = False, 
                    max_tweets: int = 20) -> List[CrawledItem]:
        """
        Scrape tweets from a specific user's profile with advanced controls.
        """
        if self.page.is_closed():
            logger.error(f"Cannot scrape @{username}: Page is closed.")
            return []

        username = username.lstrip('@')
        url = f"https://x.com/{username}"
        logger.info(f"Navigating to profile: {url} (only_new={only_new}, max_tweets={max_tweets})")
        
        last_tweet_id = self.state_manager.get_last_tweet_id(username) if only_new else None
        if last_tweet_id:
            logger.info(f"Targeting new tweets since last ID: {last_tweet_id}")

        try:
            # Add retry logic for goto
            success = False
            for attempt in range(2):
                try:
                    self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    success = True
                    break
                except Exception as e:
                    if "closed" in str(e).lower(): raise e # If page is closed, raise directly, handled by monitor layer
                    logger.warning(f"Failed to navigate to @{username} (attempt {attempt+1}): {e}")
                    self.page.wait_for_timeout(5000)
            
            if not success: return []

            # Wait for profile or error
            self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=30000)
            get_random_delay(2, 5, page=self.page)
            
            # Anti-risk: Sometimes click on a profile element or just wait
            if random.random() > 0.7:
                try:
                    self.page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                except: pass
                
        except Exception as e:
            logger.error(f"Error navigating to profile {username}: {e}")
            return []

        items = []
        scroll_count = 0
        seen_ids = set()
        stop_crawling = False
        consecutive_no_new = 0

        while len(items) < max_tweets and scroll_count < 20 and not stop_crawling:
            if self.page.is_closed(): break
            
            try:
                # Wait for tweets to load
                self.page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
                tweets = self.page.locator('article[data-testid="tweet"]').all()
                
                if not tweets:
                    if not self._check_and_retry_error():
                        consecutive_no_new += 1
                        if consecutive_no_new >= 3: break
                        self.page.mouse.wheel(0, 500)
                        self.page.wait_for_timeout(2000)
                    continue

                new_tweets_in_scroll = 0
                for tweet in tweets:
                    if len(items) >= max_tweets:
                        stop_crawling = True
                        break

                    try:
                        data = self._extract_tweet_data(tweet)
                        if not data: continue
                        
                        # Check if we reached the last seen tweet
                        if only_new and last_tweet_id and data.id == last_tweet_id:
                            logger.info(f"Reached previously seen tweet {data.id}. Stopping.")
                            stop_crawling = True
                            break

                        if data.id not in seen_ids:
                            data.source = f"profile_{username}"
                            items.append(data)
                            seen_ids.add(data.id)
                            new_tweets_in_scroll += 1
                            
                    except Exception:
                        continue

                if stop_crawling:
                    break

                # Scroll logic with human-like variability
                scroll_y = random.randint(600, 1100)
                self.page.mouse.wheel(0, scroll_y)
                get_random_delay(2, 4, page=self.page)
                scroll_count += 1
                
                # If we scroll but don't find any new items, we might have hit a wall
                if new_tweets_in_scroll == 0:
                    consecutive_no_new += 1
                else:
                    consecutive_no_new = 0
                
                if consecutive_no_new >= 5:
                    break

            except Exception as e:
                if "closed" in str(e).lower(): break
                logger.error(f"Error during scrolling/scraping profile {username}: {e}")
                break

        # Save state: update the last tweet ID to the newest one crawled
        if items:
            newest_id = items[0].id
            self.state_manager.update_last_tweet_id(username, newest_id)
            self.state_manager.save_state()

        logger.success(f"Finished scraping @{username}: {len(items)} items collected.")
        return items

    def monitor_users(self, 
                      users_config: List[Dict], 
                      global_max: int = 50) -> List[CrawledItem]:
        """
        Monitor multiple users. Recreates page if it crashes.
        """
        all_items = []
        context = self.page.context
        
        for idx, config in enumerate(users_config):
            username = config.get("username")
            if not username: continue
            
            # If current page is closed, try to open a new page to continue
            if self.page.is_closed():
                logger.warning("Browser page closed, attempting to open a new page for the next account...")
                try:
                    self.page = context.new_page()
                except Exception as e:
                    logger.error(f"Failed to open new page: {e}")
                    break

            only_new = config.get("only_new", True)
            max_tweets = config.get("max_tweets", 10)
            
            try:
                items = self.scrape_user(username, only_new=only_new, max_tweets=max_tweets)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"Critical error while monitoring @{username}: {e}")
            
            # Anti-risk: delay between users
            if len(users_config) > 1 and idx != len(users_config) - 1:
                delay = random.uniform(5, 15)
                logger.info(f"Waiting {delay:.1f}s before next profile...")
                
                # Anti-memory leak and anti-tracking: jump back to about:blank to release resources loaded by previous account
                try:
                    if not self.page.is_closed():
                        self.page.goto("about:blank")
                except Exception:
                    pass
                
                self.page.wait_for_timeout(int(delay * 1000))
                
            if len(all_items) >= global_max:
                logger.warning(f"Global max items ({global_max}) reached.")
                break
                
        return all_items
