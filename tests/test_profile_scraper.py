import pytest
from unittest.mock import MagicMock, patch
from x_crawlfox.scrapers.x.profile import ProfileScraper
from x_crawlfox.models.schema import CrawledItem, AuthorInfo, DataStats

def mock_tweet(tweet_id, content="test content"):
    item = MagicMock(spec=CrawledItem)
    item.id = tweet_id
    item.content = content
    item.author = AuthorInfo(nickname="test", username="test")
    item.stats = DataStats()
    return item

@patch("x_crawlfox.scrapers.x.profile.StateManager")
def test_scrape_user_only_new(mock_state_class):
    """测试 only_new 模式下遇到旧推文是否停止。"""
    # 模拟 StateManager 返回上次看到的 ID
    mock_state = mock_state_class.return_value
    mock_state.get_last_tweet_id.return_value = "old_id"
    
    mock_page = MagicMock()
    scraper = ProfileScraper(mock_page)
    
    # 模拟 _extract_tweet_data 依次返回新、旧推文
    new_item = mock_tweet("new_id")
    old_item = mock_tweet("old_id")
    
    scraper._extract_tweet_data = MagicMock(side_effect=[new_item, old_item])
    
    # 模拟页面上有两个推文节点
    mock_tweets = [MagicMock(), MagicMock()]
    mock_page.locator.return_value.all.return_value = mock_tweets
    
    results = scraper.scrape_user("testuser", only_new=True)
    
    # 应该只返回 new_id 那个，遇到 old_id 就停了
    assert len(results) == 1
    assert results[0].id == "new_id"

@patch("x_crawlfox.scrapers.x.profile.StateManager")
def test_scrape_user_max_tweets(mock_state_class):
    """测试 max_tweets 限制。"""
    mock_page = MagicMock()
    scraper = ProfileScraper(mock_page)
    
    # 模拟产生 5 个推文，但 max_tweets 设为 2
    scraper._extract_tweet_data = MagicMock(side_effect=[
        mock_tweet("id1"), mock_tweet("id2"), mock_tweet("id3")
    ])
    
    mock_page.locator.return_value.all.return_value = [MagicMock(), MagicMock(), MagicMock()]
    
    results = scraper.scrape_user("testuser", max_tweets=2)
    
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[1].id == "id2"

@patch("x_crawlfox.scrapers.x.profile.StateManager")
def test_monitor_users_flow(mock_state_class):
    """测试监控多账号循环。"""
    mock_page = MagicMock()
    scraper = ProfileScraper(mock_page)
    
    # 模拟 scrape_user 返回结果
    scraper.scrape_user = MagicMock(side_effect=[
        [mock_tweet("u1_1")], [mock_tweet("u2_1")]
    ])
    
    config = [
        {"username": "user1", "max_tweets": 5},
        {"username": "user2", "max_tweets": 5}
    ]
    
    with patch("time.sleep"): # 避免测试中等待
        results = scraper.monitor_users(config)
    
    assert len(results) == 2
    assert scraper.scrape_user.call_count == 2
