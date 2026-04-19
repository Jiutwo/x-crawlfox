import os
import random
from pathlib import Path
from typing import Optional, Dict, Any
from camoufox import Camoufox
from loguru import logger

from .base_scraper import BaseScraper
from ..utils.auth import ensure_storage_state

class BrowserManager:
    def __init__(self, 
                 auth_file: Optional[str] = None,
                 headless: bool = True,
                 proxy: Optional[str] = None):
        self.auth_file = Path(auth_file) if auth_file else None
        self.headless = headless
        self.proxy = proxy
        self.browser: Optional[Camoufox] = None
        self.context = None

    def __enter__(self):
        proxy_config = None
        if self.proxy:
            proxy_config = {"server": self.proxy}
            logger.info(f"Using proxy: {self.proxy}")

        self.browser = Camoufox(headless=self.headless, humanize=True).__enter__()
        
        # Load storage state if it exists
        storage_state = None
        if self.auth_file and self.auth_file.exists():
            # Auto-detect and convert format
            ensure_storage_state(self.auth_file)
            logger.info(f"Loading auth state from {self.auth_file}")
            storage_state = str(self.auth_file)
        elif self.auth_file:
            # Explicitly provided but file is missing
            logger.warning(f"Auth file {self.auth_file} not found. You may need to login first.")

        self.context = self.browser.new_context(
            storage_state=storage_state,
            proxy=proxy_config
        )
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.__exit__(exc_type, exc_val, exc_tb)

    def save_auth_state(self, path: Optional[str] = None):
        if not self.context:
            logger.error("No active context to save auth state from.")
            return
        
        save_path = Path(path) if path else self.auth_file
        save_path.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(save_path))
        logger.info(f"Auth state saved to {save_path}")

def get_random_delay(min_delay: float = 2.0, max_delay: float = 5.0, page: Optional[Any] = None):
    delay = random.uniform(min_delay, max_delay)
    if page and hasattr(page, "wait_for_timeout"):
        page.wait_for_timeout(int(delay * 1000))
    else:
        import time
        time.sleep(delay)
    return delay
