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
            logger.error("浏览器页面已关闭，无法重试。")
            return False

        for i in range(retry_count):
            try:
                retry_button = self.page.locator('button:has-text("Retry"), button:has-text("重试")')
                error_text = self.page.locator('text="Something went wrong"')

                if error_text.is_visible() or retry_button.is_visible():
                    logger.warning(f"检测到 X 页面异常 (风控/限流)，第 {i+1} 次尝试恢复...")
                    if retry_button.is_visible():
                        retry_button.click()
                    else:
                        self.page.reload(wait_until="networkidle")

                    # Human-like delay using Playwright's wait_for_timeout
                    self.page.wait_for_timeout(random.randint(3000, 6000))

                    # Check if fixed
                    if self.page.locator('article[data-testid="tweet"]').first.is_visible():
                        logger.success("页面恢复正常。")
                        return True
                else:
                    if "login" in self.page.url:
                        logger.error("检测到会话失效，强制要求登录。")
                        return False
                    return True
            except Exception as e:
                logger.debug(f"检查页面错误时发生异常 (可能页面已关闭): {e}")
                return False
        return False

