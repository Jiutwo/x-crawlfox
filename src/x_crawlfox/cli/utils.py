from pathlib import Path
from typing import Any, List
from datetime import datetime
from loguru import logger
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError


def handle_error(e: Exception):
    if isinstance(e, PlaywrightTimeoutError):
        logger.error("Connection timeout! Please check your network environment (VPN?) or proxy settings (--proxy).")
        logger.debug(f"Detailed error: {e}")
    elif isinstance(e, PlaywrightError):
        logger.error(f"Browser automation error: {e.message}")
        if "executable" in e.message.lower():
            logger.info("Tip: try running 'playwright install' to install required browser drivers.")
    elif isinstance(e, KeyboardInterrupt):
        logger.warning("Operation aborted by user.")
    else:
        logger.exception(f"An unknown error occurred: {e}")


def save_items(items: List[Any], filename: str, output_dir: str = "output"):
    save_path_dir = Path(output_dir)
    save_path_dir.mkdir(parents=True, exist_ok=True)

    if not filename.endswith(".jsonl"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = save_path_dir / f"{filename}_{timestamp}.jsonl"
    else:
        filepath = save_path_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")

    logger.info(f"Save successful! {len(items)} items saved to {filepath}")
