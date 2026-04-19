"""
Tests verifying that every new engine (those without simulate mode) falls
back to fast mode when scrape_simulate() is called.

All new scrapers set:
    home_url = ""
    search_input_selectors = []

This means _find_search_input() always returns None, so the base class
scrape_simulate() delegates to scrape_fast() automatically.
"""
import pytest
from unittest.mock import MagicMock, patch

from x_crawlfox.models.search_schema import SearchMode, SearchFilter

from x_crawlfox.scrapers.search.engines.bing_cn import BingCNSearchScraper
from x_crawlfox.scrapers.search.engines.bing_int import BingINTSearchScraper
from x_crawlfox.scrapers.search.engines.so360 import So360SearchScraper
from x_crawlfox.scrapers.search.engines.sogou import SogouSearchScraper
from x_crawlfox.scrapers.search.engines.wechat import WeChatSearchScraper
from x_crawlfox.scrapers.search.engines.toutiao import ToutiaoSearchScraper
from x_crawlfox.scrapers.search.engines.jisilu import JisiluSearchScraper
from x_crawlfox.scrapers.search.engines.google_hk import GoogleHKSearchScraper
from x_crawlfox.scrapers.search.engines.duckduckgo import DuckDuckGoSearchScraper
from x_crawlfox.scrapers.search.engines.yahoo import YahooSearchScraper
from x_crawlfox.scrapers.search.engines.startpage import StartpageSearchScraper
from x_crawlfox.scrapers.search.engines.brave import BraveSearchScraper
from x_crawlfox.scrapers.search.engines.ecosia import EcosiaSearchScraper
from x_crawlfox.scrapers.search.engines.qwant import QwantSearchScraper
from x_crawlfox.scrapers.search.engines.wolframalpha import WolframAlphaSearchScraper


# Engines that use only the base fallback (no search_input_selectors).
FALLBACK_ONLY_ENGINES = [
    BingCNSearchScraper,
    BingINTSearchScraper,
    So360SearchScraper,
    SogouSearchScraper,
    WeChatSearchScraper,
    GoogleHKSearchScraper,
    DuckDuckGoSearchScraper,
    YahooSearchScraper,
    BraveSearchScraper,
    EcosiaSearchScraper,
    WolframAlphaSearchScraper,
]

# Engines that implement scrape_simulate() with real selectors but still fall
# back to scrape_fast() when no input element is found on the page.
SIMULATE_CAPABLE_ENGINES = [
    ToutiaoSearchScraper,
    JisiluSearchScraper,
    StartpageSearchScraper,
    QwantSearchScraper,
]

ALL_ENGINE_CLASSES = FALLBACK_ONLY_ENGINES + SIMULATE_CAPABLE_ENGINES


@pytest.mark.parametrize("engine_cls", FALLBACK_ONLY_ENGINES, ids=lambda c: c.__name__)
class TestSimulateFallback:
    """Engines that have no simulate selectors must fall back to fast mode."""

    def test_has_no_simulate_selectors(self, engine_cls):
        scraper = engine_cls(MagicMock())
        assert scraper.search_input_selectors == [], (
            f"{engine_cls.__name__} should have empty search_input_selectors"
        )

    def test_find_search_input_returns_none(self, engine_cls):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 0
        scraper = engine_cls(page)
        assert scraper._find_search_input() is None

    def test_simulate_delegates_to_fast(self, engine_cls):
        """Calling scrape_simulate() must ultimately call scrape_fast()."""
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 0
        scraper = engine_cls(page)

        with patch.object(scraper, "scrape_fast", return_value=[]) as mock_fast:
            scraper.scrape_simulate("python", None, 5)

        mock_fast.assert_called_once_with("python", None, 5)

    def test_scrape_with_simulate_mode_returns_list(self, engine_cls):
        """scrape(..., mode=SIMULATE) must return a list (possibly empty)."""
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 0
        scraper = engine_cls(page)

        with patch.object(scraper, "scrape_fast", return_value=[]):
            results = scraper.scrape("python", mode=SearchMode.SIMULATE)

        assert isinstance(results, list)


@pytest.mark.parametrize("engine_cls", SIMULATE_CAPABLE_ENGINES, ids=lambda c: c.__name__)
class TestSimulateCapable:
    """Engines with real simulate mode: must have selectors and fall back when no input."""

    def test_has_simulate_selectors(self, engine_cls):
        scraper = engine_cls(MagicMock())
        assert scraper.search_input_selectors != [], (
            f"{engine_cls.__name__} should define search_input_selectors"
        )

    def test_find_search_input_returns_none_when_no_input(self, engine_cls):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 0
        scraper = engine_cls(page)
        assert scraper._find_search_input() is None

    def test_simulate_falls_back_to_fast_when_no_input(self, engine_cls):
        page = MagicMock()
        page.locator.return_value.first.count.return_value = 0
        scraper = engine_cls(page)

        with patch.object(scraper, "scrape_fast", return_value=[]) as mock_fast:
            scraper.scrape_simulate("python", None, 5)

        mock_fast.assert_called_once_with("python", None, 5)


@pytest.mark.parametrize("engine_cls", ALL_ENGINE_CLASSES, ids=lambda c: c.__name__)
class TestEngineMetadata:
    """Basic metadata checks that apply to every new engine."""

    def test_engine_name_is_non_empty_string(self, engine_cls):
        scraper = engine_cls(MagicMock())
        assert isinstance(scraper.engine_name, str) and scraper.engine_name

    def test_build_search_url_returns_https_url(self, engine_cls):
        scraper = engine_cls(MagicMock())
        url = scraper.build_search_url("python", None)
        assert url.startswith("https://"), f"{engine_cls.__name__}.build_search_url must return HTTPS URL"

    def test_build_search_url_contains_keyword(self, engine_cls):
        scraper = engine_cls(MagicMock())
        url = scraper.build_search_url("uniqueterm", None)
        assert "uniqueterm" in url, (
            f"{engine_cls.__name__}.build_search_url must embed the keyword"
        )

    def test_build_search_url_encodes_spaces(self, engine_cls):
        scraper = engine_cls(MagicMock())
        url = scraper.build_search_url("hello world", None)
        # URL must not contain a raw space
        assert " " not in url, (
            f"{engine_cls.__name__}.build_search_url must URL-encode spaces"
        )

    def test_extract_results_returns_list_on_empty_page(self, engine_cls):
        page = MagicMock()
        page.locator.return_value.all.return_value = []
        scraper = engine_cls(page)
        results = scraper.extract_results("q", SearchMode.FAST, 10)
        assert isinstance(results, list)
