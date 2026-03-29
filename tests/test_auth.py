import json
import pytest
from pathlib import Path

from x_crawlfox.utils.auth import (
    is_cookie_editor_format,
    convert_to_playwright_format,
    ensure_storage_state
)


@pytest.fixture
def cookie_editor_data():
    return [
        {
            "domain": ".x.com",
            "expirationDate": 1803523617.603304,
            "hostOnly": False,
            "httpOnly": True,
            "name": "auth_token",
            "path": "/",
            "sameSite": "no_restriction",
            "secure": True,
            "session": False,
            "value": "test_token"
        }
    ]

@pytest.fixture
def playwright_data():
    return {
        "cookies": [
            {
                "name": "auth_token",
                "value": "test_token",
                "domain": ".x.com",
                "path": "/",
                "expires": 1803523617.603304,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None"
            }
        ],
        "origins": []
    }

def test_is_cookie_editor_format(cookie_editor_data, playwright_data):
    # 正确识别
    assert is_cookie_editor_format(cookie_editor_data) is True
    # 已经是 Playwright 格式不应被误判
    assert is_cookie_editor_format(playwright_data) is False
    # 空列表或非列表不应误判
    assert is_cookie_editor_format([]) is False
    assert is_cookie_editor_format({}) is False

def test_convert_to_playwright_format(cookie_editor_data):
    # 修改一个 sameSite 为 lax 来测试不同映射
    cookie_editor_data.append({
        "name": "guest_id",
        "value": "v1_123",
        "domain": ".x.com",
        "path": "/",
        "sameSite": "lax",
        "expirationDate": 1700000000
    })
    
    result = convert_to_playwright_format(cookie_editor_data)
    
    assert "cookies" in result
    assert len(result["cookies"]) == 2
    
    # 验证第一个 cookie (no_restriction -> None)
    c1 = result["cookies"][0]
    assert c1["name"] == "auth_token"
    assert c1["expires"] == 1803523617.603304
    assert c1["sameSite"] == "None"
    
    # 验证第二个 cookie (lax -> Lax)
    c2 = result["cookies"][1]
    assert c2["sameSite"] == "Lax"

def test_ensure_storage_state(tmp_path, cookie_editor_data):
    # 创建一个临时的 Cookie-Editor 格式文件
    test_file = tmp_path / "test_auth.json"
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(cookie_editor_data, f)
    
    # 执行确保逻辑
    ensure_storage_state(test_file)
    
    # 读取回来看是否已转换
    with open(test_file, "r", encoding="utf-8") as f:
        new_data = json.load(f)
    
    assert isinstance(new_data, dict)
    assert "cookies" in new_data
    assert new_data["cookies"][0]["name"] == "auth_token"
    assert "expires" in new_data["cookies"][0]
