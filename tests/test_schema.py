import json
from datetime import datetime, timezone
from x_crawlfox.models.schema import CrawledItem, AuthorInfo, DataStats

def test_time_serialization_unification():
    # 创建一个具有微秒的时间对象
    dt = datetime(2026, 3, 25, 22, 0, 42, 469679, tzinfo=timezone.utc)
    
    author = AuthorInfo(nickname="test", username="testuser")
    stats = DataStats()
    
    item = CrawledItem(
        id="123",
        content="test content",
        author=author,
        stats=stats,
        publish_time=dt,
        crawl_time=dt,
        source="test"
    )
    
    # 序列化为 JSON
    data = json.loads(item.model_dump_json())
    
    # 验证格式是否统一为 YYYY-MM-DDTHH:MM:SSZ
    expected_format = "2026-03-25T22:00:42Z"
    
    assert data["publish_time"] == expected_format
    assert data["crawl_time"] == expected_format
    assert "Z" in data["publish_time"]
    assert "." not in data["publish_time"] # 确保没有微秒
