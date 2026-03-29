import os
from pathlib import Path
from loguru import logger

def get_data_dir() -> Path:
    """
    获取数据存储目录逻辑：
    1. 优先检查当前运行目录下是否存在 .x-crawlfox
    2. 如果没有，则使用用户主目录下的 ~/.x-crawlfox
    """
    # 1. 检查当前目录
    local_dir = Path(".x-crawlfox")
    if local_dir.exists() and local_dir.is_dir():
        return local_dir.absolute()
    
    # 2. 回退到用户主目录
    home_dir = Path.home() / ".x-crawlfox"
    
    # 确保目录存在
    if not home_dir.exists():
        try:
            home_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"已创建全局配置目录: {home_dir}")
        except Exception as e:
            logger.error(f"创建配置目录失败: {e}")
            # 最后的兜底使用当前目录
            return Path(".").absolute()
            
    return home_dir.absolute()

def get_auth_path() -> Path:
    """获取浏览器会话存储路径"""
    return get_data_dir() / "storage_state.json"

def get_state_path() -> Path:
    """获取爬取进度存储路径"""
    return get_data_dir() / "crawler_state.json"
