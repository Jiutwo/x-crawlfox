from pydantic import BaseModel, Field, field_serializer
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class SearchMode(str, Enum):
    SIMULATE = "simulate"
    FAST = "fast"


class TimeRange(str, Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class SearchFilter(BaseModel):
    time_range: Optional[TimeRange] = None
    site: Optional[str] = None
    filetype: Optional[str] = None
    exact_phrase: Optional[str] = None
    exclude_terms: Optional[List[str]] = None
    language: Optional[str] = None


class SearchResult(BaseModel):
    rank: int
    title: str
    url: str
    description: Optional[str] = None
    engine: str
    keyword: str
    mode: SearchMode
    crawl_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data: Optional[Dict[str, Any]] = None

    @field_serializer("crawl_time")
    def serialize_dt(self, dt: datetime, _info):
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
