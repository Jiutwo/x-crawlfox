import random
import time
from abc import ABC, abstractmethod
from typing import List, Any
from playwright.sync_api import Page
from loguru import logger
from ..models.schema import CrawledItem

class BaseScraper(ABC):
    def __init__(self, page: Page):
        self.page = page

    @abstractmethod
    def scrape(self, **kwargs) -> List[CrawledItem]:
        """
        Execute the scraping logic.
        """
        pass

    def _check_and_retry_error(self, retry_count: int = 2) -> bool:
        """检测并尝试修复页面错误（如风控拦截）"""
        if self.page.is_closed():
            logger.error("Browser page is closed, cannot retry.")
            return False

        for i in range(retry_count):
            try:
                retry_button = self.page.locator('button:has-text("Retry"), button:has-text("重试")')
                error_text = self.page.locator('text="Something went wrong"')

                if error_text.is_visible() or retry_button.is_visible():
                    logger.warning(f"X page abnormality detected (rate limit/risk control), recovery attempt {i+1}...")
                    if retry_button.is_visible():
                        retry_button.click()
                    else:
                        self.page.reload(wait_until="networkidle")

                    # Human-like delay using Playwright's wait_for_timeout
                    self.page.wait_for_timeout(random.randint(3000, 6000))

                    # Check if fixed
                    if self.page.locator('article[data-testid="tweet"]').first.is_visible():
                        logger.success("Page recovered successfully.")
                        return True
                else:
                    if "login" in self.page.url:
                        logger.error("Session expiration detected, login is forced.")
                        return False
                    return True
            except Exception as e:
                logger.debug(f"Exception occurred while checking for page errors (page might be closed): {e}")
                return False
        return False

