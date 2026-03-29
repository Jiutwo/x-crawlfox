import json
from pathlib import Path
from x_crawlfox.utils.state import StateManager

def test_state_manager_lifecycle(tmp_path):
    """测试 StateManager 的加载、更新和保存逻辑。"""
    state_file = tmp_path / "test_state.json"
    
    # 1. 初始状态
    manager = StateManager(state_file=str(state_file))
    assert manager.get_last_tweet_id("user1") is None
    
    # 2. 更新状态
    manager.update_last_tweet_id("user1", "12345")
    assert manager.get_last_tweet_id("user1") == "12345"
    
    # 3. 保存并重新加载
    manager.save_state()
    assert state_file.exists()
    
    new_manager = StateManager(state_file=str(state_file))
    assert new_manager.get_last_tweet_id("user1") == "12345"

def test_state_manager_update_existing(tmp_path):
    """测试更新现有账号的状态。"""
    state_file = tmp_path / "test_state.json"
    manager = StateManager(state_file=str(state_file))
    
    manager.update_last_tweet_id("user1", "100")
    manager.update_last_tweet_id("user1", "200")
    
    assert manager.get_last_tweet_id("user1") == "200"
