"""Tests for search engine data models (search_schema.py)."""
import json
from datetime import datetime, timezone
from x_crawlfox.models.search_schema import (
    SearchMode,
    TimeRange,
    SearchFilter,
    SearchResult,
)


# ---------------------------------------------------------------------------
# SearchMode / TimeRange enum values
# ---------------------------------------------------------------------------

def test_search_mode_values():
    assert SearchMode.SIMULATE == "simulate"
    assert SearchMode.FAST == "fast"


def test_time_range_values():
    assert TimeRange.HOUR == "hour"
    assert TimeRange.DAY == "day"
    assert TimeRange.WEEK == "week"
    assert TimeRange.MONTH == "month"
    assert TimeRange.YEAR == "year"


# ---------------------------------------------------------------------------
# SearchFilter defaults and population
# ---------------------------------------------------------------------------

def test_search_filter_all_defaults_none():
    f = SearchFilter()
    assert f.time_range is None
    assert f.site is None
    assert f.filetype is None
    assert f.exact_phrase is None
    assert f.exclude_terms is None
    assert f.language is None


def test_search_filter_with_values():
    f = SearchFilter(
        time_range=TimeRange.WEEK,
        site="github.com",
        filetype="pdf",
        exact_phrase="machine learning",
        exclude_terms=["spam", "ads"],
        language="en",
    )
    assert f.time_range == TimeRange.WEEK
    assert f.site == "github.com"
    assert f.filetype == "pdf"
    assert f.exact_phrase == "machine learning"
    assert f.exclude_terms == ["spam", "ads"]
    assert f.language == "en"


# ---------------------------------------------------------------------------
# SearchResult instantiation and serialization
# ---------------------------------------------------------------------------

def test_search_result_required_fields():
    r = SearchResult(
        rank=1,
        title="Test Title",
        url="https://example.com",
        engine="baidu",
        keyword="test",
        mode=SearchMode.FAST,
    )
    assert r.rank == 1
    assert r.title == "Test Title"
    assert r.url == "https://example.com"
    assert r.engine == "baidu"
    assert r.keyword == "test"
    assert r.mode == SearchMode.FAST
    assert r.description is None
    assert r.raw_data is None


def test_search_result_crawl_time_serialization():
    """crawl_time must be serialized as YYYY-MM-DDTHH:MM:SSZ (no microseconds)."""
    dt = datetime(2026, 4, 13, 10, 30, 0, 999999, tzinfo=timezone.utc)
    r = SearchResult(
        rank=1,
        title="T",
        url="https://x.com",
        engine="google",
        keyword="kw",
        mode=SearchMode.FAST,
        crawl_time=dt,
    )
    data = json.loads(r.model_dump_json())
    assert data["crawl_time"] == "2026-04-13T10:30:00Z"
    assert "." not in data["crawl_time"]


def test_search_result_with_description_and_raw_data():
    r = SearchResult(
        rank=3,
        title="Some Page",
        url="https://example.com/page",
        description="A useful snippet.",
        engine="bing",
        keyword="query",
        mode=SearchMode.SIMULATE,
        raw_data={"extra": "value"},
    )
    data = json.loads(r.model_dump_json())
    assert data["description"] == "A useful snippet."
    assert data["raw_data"] == {"extra": "value"}
