import base64
import json
from unittest.mock import MagicMock
from x_crawlfox.scrapers.x.news import NewsScraper

def test_extract_news_article_data_with_base64_id():
    """
    测试能够成功解析 Base64 ID 并生成正确的 trending URL。
    """
    mock_page = MagicMock()
    scraper = NewsScraper(mock_page)
    
    # 模拟 article Locator
    mock_article = MagicMock()
    # 设置测试用的 data-testid (Base64 解码后为 AiTrend:2036561679333597521)
    mock_article.get_attribute.return_value = "news_sidebar_article_QWlUcmVuZDoyMDM2NTYxNjc5MzMzNTk3NTIx"
    
    # 模拟子元素的定位器行为
    def mock_locator(selector):
        m = MagicMock()
        m.count.return_value = 1
        if "css-1jxf684" in selector: # 标题
            m.inner_text.return_value = "AI News Title"
        elif "color: rgb(113, 118, 123)" in selector: # 元数据
            m.inner_text.return_value = "2 hours ago · News · 10.5K posts"
        return MagicMock(first=m)

    mock_article.locator.side_effect = mock_locator

    # 执行私有解析方法（测试核心逻辑）
    item = scraper._extract_news_article_data(mock_article)
    
    assert item is not None
    assert item.id == "2036561679333597521"
    assert item.url == "https://x.com/i/trending/2036561679333597521"
    assert item.title == "AI News Title"
    # 验证帖子数成功解析并存入 comments
    assert item.stats.comments == 10500

def test_extract_news_article_data_fallback():
    """
    测试当 Base64 ID 无效时，能够成功触发 Fallback 机制（生成搜索链接）。
    """
    mock_page = MagicMock()
    scraper = NewsScraper(mock_page)
    
    mock_article = MagicMock()
    # 故意设置一个错误的 testid
    mock_article.get_attribute.return_value = "news_sidebar_article_INVALID_BASE64"
    
    def mock_locator(selector):
        m = MagicMock()
        m.count.return_value = 1
        if "css-1jxf684" in selector:
            m.inner_text.return_value = "Google TurboQuant News"
        else:
            m.inner_text.return_value = ""
        return MagicMock(first=m)

    mock_article.locator.side_effect = mock_locator

    item = scraper._extract_news_article_data(mock_article)
    
    assert item is not None
    # 验证 ID 是通过哈希生成的（16位）
    assert len(item.id) == 16
    # 验证 URL 变成了搜索链接 (当前实现保留原始空格)
    assert item.url == "https://x.com/search?q=Google TurboQuant News"
