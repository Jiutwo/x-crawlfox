import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from x_crawlfox.core.base_scraper import BaseScraper

class ConcreteScraper(BaseScraper):
    def scrape(self, **kwargs):
        return []

def test_check_and_retry_error_visible():
    """测试当错误提示可见时，重试逻辑是否触发 reload。"""
    mock_page = MagicMock()
    scraper = ConcreteScraper(mock_page)
    
    # 模拟 url 属性，确保不包含 login
    type(mock_page).url = PropertyMock(return_value="https://x.com/home")
    
    # 模拟 locator 行为
    mock_retry_btn = MagicMock()
    mock_error_text = MagicMock()
    mock_tweet = MagicMock()
    
    # 第一次检查：重试按钮不可见，错误文本可见
    mock_retry_btn.is_visible.return_value = False
    mock_error_text.is_visible.return_value = True
    
    # 重试后最后的检查：推文可见
    mock_tweet.first.is_visible.return_value = True

    def side_effect_visible(*args, **kwargs):
        if 'text="Something went wrong"' in args[0]:
            return mock_error_text
        if 'Retry' in args[0]:
            return mock_retry_btn
        if 'tweet' in args[0]:
            return mock_tweet
        return MagicMock()

    mock_page.locator.side_effect = side_effect_visible
    
    with patch("time.sleep"):
        # retry_count=1 意味着只跑一轮循环
        success = scraper._check_and_retry_error(retry_count=1)
    
    assert mock_page.reload.called
    assert success is True

def test_check_and_retry_error_not_needed():
    """测试没有错误时直接返回 True。"""
    mock_page = MagicMock()
    scraper = ConcreteScraper(mock_page)
    
    # 确保不包含 login
    type(mock_page).url = PropertyMock(return_value="https://x.com/home")
    
    # 模拟 locator
    mock_locator = MagicMock()
    mock_locator.is_visible.return_value = False
    mock_page.locator.return_value = mock_locator
    
    success = scraper._check_and_retry_error()
    assert success is True
