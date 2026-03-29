import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger

def parse_relative_time(time_str: str) -> Optional[datetime]:
    """
    Parses a relative time string like '2 days ago', '7 hours ago', '30 minutes ago'
    into an absolute UTC datetime.
    Returns None if the string cannot be parsed.
    """
    if not time_str:
        return None
    
    # Try ISO format first
    try:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        pass

    pattern = r'(\d+)\s+(second|minute|hour|day|week)s?\s+ago'
    match = re.search(pattern, time_str.lower())
    if not match:
        return None
    
    amount = int(match.group(1))
    unit = match.group(2)
    delta_map = {
        'second': timedelta(seconds=amount),
        'minute': timedelta(minutes=amount),
        'hour': timedelta(hours=amount),
        'day': timedelta(days=amount),
        'week': timedelta(weeks=amount),
    }
    return datetime.now(timezone.utc) - delta_map[unit]

def parse_metric_text(text: str) -> int:
    """
    Parse metric text (e.g., '1.2K', '1M') into an integer.
    """
    if not text:
        return 0
    
    text = text.upper().strip()
    multiplier = 1
    
    if text.endswith('K'):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith('M'):
        multiplier = 1000000
        text = text[:-1]
    elif text.endswith('B'):
        multiplier = 1000000000
        text = text[:-1]
        
    try:
        # Remove commas and other non-numeric chars except decimal point
        clean_text = re.sub(r'[^\d.]', '', text)
        if not clean_text:
            return 0
        value = float(clean_text)
        return int(value * multiplier)
    except ValueError:
        return 0
