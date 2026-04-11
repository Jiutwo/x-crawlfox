from pydantic import BaseModel, Field, field_serializer
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from enum import Enum

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    ARTICLE = "article"

class MediaResource(BaseModel):
    type: MediaType
    url: str
    cover_url: Optional[str] = None
    is_cover: bool = False

class DataStats(BaseModel):
    likes: int = 0
    comments: int = 0
    shares: int = 0
    collects: int = 0
    views: int = 0

class AuthorInfo(BaseModel):
    nickname: str
    username: str
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None

class CrawledItem(BaseModel):
    id: str
    platform: str = "x"
    url: Optional[str] = None   # Link
    title: Optional[str] = None # Title
    content: str                # Detailed content
    description: Optional[str] = None # Summary description
    author: AuthorInfo
    media: List[MediaResource] = []
    stats: DataStats
    publish_time: Optional[datetime] = None
    crawl_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str # e.g., 'following', 'for_you', 'news', 'profile'
    is_article: bool = False
    raw_data: Optional[Dict[str, Any]] = None

    @field_serializer('publish_time', 'crawl_time')
    def serialize_dt(self, dt: datetime, _info):
        if dt is None:
            return None
        # Force conversion to UTC, remove microseconds, and append Z
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
