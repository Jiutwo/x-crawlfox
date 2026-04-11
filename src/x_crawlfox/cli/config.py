import json
from pathlib import Path

class ConfigManager:
    def __init__(self):
        """Manage configuration folder paths"""
        self.local_dir = Path.cwd() / ".x-crawlfox"
        self.global_dir = Path.home() / ".x-crawlfox"
        
        self.config_dir = self.get_config_dir()
        
        # Define validation file paths
        self.auth_path = self.config_dir / "x_cookies.json"
        
    def ensure_dirs(self):
        """Automatically create all required directories, user does not need to manually create them"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
    def get_config_dir(self):
        """Return current directory path if .x-crawlfox is in current directory; otherwise return user directory path"""
        if self.local_dir.exists():
            return self.local_dir
        else:
            return self.global_dir
        
    def get_crawl_config_path(self):
        """Get crawl config file path"""
        config_dir = self.get_config_dir()
        return Path(config_dir) / "crawl_config.json"
    
    def get_x_crawl_state_path(self):
        return self.get_config_dir() / "x_crawl_state.json"
        
    def get_default_config(self) -> dict:
        return {
            "global": {"output_dir": "output", "headless": True},
            "x": {
                "timeline": [
                    {"type": "For you", "max_items": 10},
                    {"type": "Following", "max_items": 10},
                ],
                "news": {"enabled": True, "detail": True, "max_items": 5}
            }
        }

    @staticmethod
    def init_config(global_mode: bool) -> str:
        base_dir = Path.home() / ".x-crawlfox" if global_mode else Path.cwd() / ".x-crawlfox"
        base_dir.mkdir(parents=True, exist_ok=True)

        default_config = {
            "global": {"output_dir": "output", "headless": True},
            "x": {
                "timeline": [
                    {"type": "For you", "max_items": 10},
                    {"type": "Following", "max_items": 10},
                ],
                "news": {"enabled": True, "detail": False, "max_items": 5}
            }
        }

        config_file = base_dir / "crawl_config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)

        return base_dir


config_manager = ConfigManager()