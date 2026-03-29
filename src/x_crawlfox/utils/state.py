import json
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime

from .paths import get_state_path

class StateManager:
    def __init__(self, state_file: Optional[str] = None):
        self.state_file = Path(state_file) if state_file else get_state_path()
        self.state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading state file: {e}")
            return {}

    def save_state(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def get_last_tweet_id(self, username: str) -> Optional[str]:
        return self.state.get(username, {}).get("last_tweet_id")

    def update_last_tweet_id(self, username: str, tweet_id: str):
        if username not in self.state:
            self.state[username] = {}
        self.state[username]["last_tweet_id"] = tweet_id
        self.state[username]["last_crawl_time"] = datetime.now().isoformat()
