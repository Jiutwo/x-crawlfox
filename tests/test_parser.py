from datetime import datetime, timezone, timedelta
from x_crawlfox.utils.parser import parse_relative_time, parse_metric_text

def test_parse_relative_time():
    now = datetime.now(timezone.utc)
    
    # Test "2 days ago"
    res = parse_relative_time("2 days ago")
    assert res is not None
    # Check if the difference is approximately 2 days (within 5 seconds)
    diff = abs((now - res).total_seconds() - 2 * 24 * 3600)
    assert diff < 5
    
    # Test "5 hours ago"
    res = parse_relative_time("5 hours ago")
    assert res is not None
    diff = abs((now - res).total_seconds() - 5 * 3600)
    assert diff < 5

def test_parse_metric_text():
    assert parse_metric_text("1.2K") == 1200
    assert parse_metric_text("1M") == 1000000
    assert parse_metric_text("5.5B") == 5500000000
    assert parse_metric_text("123") == 123
    assert parse_metric_text("1,234") == 1234
    assert parse_metric_text("") == 0
