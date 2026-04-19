"""
Unit tests for international search engine scrapers:
  Google HK, DuckDuckGo, Yahoo, Startpage, Brave, Ecosia, Qwant, WolframAlpha

All Playwright interactions are replaced with MagicMock objects.
"""
from unittest.mock import MagicMock, patch

from x_crawlfox.models.search_schema import SearchMode, TimeRange, SearchFilter, SearchResult
from x_crawlfox.scrapers.search.engines.google_hk import GoogleHKSearchScraper
from x_crawlfox.scrapers.search.engines.duckduckgo import DuckDuckGoSearchScraper
from x_crawlfox.scrapers.search.engines.yahoo import YahooSearchScraper
from x_crawlfox.scrapers.search.engines.startpage import StartpageSearchScraper
from x_crawlfox.scrapers.search.engines.brave import BraveSearchScraper
from x_crawlfox.scrapers.search.engines.ecosia import EcosiaSearchScraper
from x_crawlfox.scrapers.search.engines.qwant import QwantSearchScraper
from x_crawlfox.scrapers.search.engines.wolframalpha import WolframAlphaSearchScraper

from .conftest import (
    page_with_results,
    page_no_results,
    make_item,
    make_item_with_title_el,
    make_wa_page,
    make_qwant_page,
    make_startpage_page,
)


# ===========================================================================
# Google HK  (inherits extract_results from GoogleSearchScraper)
# ===========================================================================

class TestGoogleHKUrl:
    def setup_method(self):
        self.scraper = GoogleHKSearchScraper(MagicMock())

    def test_url_uses_google_hk_domain(self):
        url = self.scraper.build_search_url("python", None)
        assert "google.com.hk/search?q=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("AI Agent", None)
        assert "AI" in url

    def test_time_range_adds_tbs_param(self):
        f = SearchFilter(time_range=TimeRange.WEEK)
        url = self.scraper.build_search_url("news", f)
        assert "tbs=qdr:w" in url

    def test_language_filter_adds_lr_param(self):
        f = SearchFilter(language="zh-TW")
        url = self.scraper.build_search_url("news", f)
        assert "lr=lang_zh-TW" in url

    def test_differs_from_google_com(self):
        from x_crawlfox.scrapers.search.engines.google import GoogleSearchScraper
        g = GoogleSearchScraper(MagicMock()).build_search_url("q", None)
        hk = self.scraper.build_search_url("q", None)
        assert "google.com/search" in g
        assert "google.com.hk/search" in hk


# ===========================================================================
# DuckDuckGo
# ===========================================================================

def _make_ddg_item(title="DDG Result", href="https://example.com", desc=None, has_link=True):
    # The scraper calls item.locator(".result__snippet, .snippet") — one combined selector string
    return make_item(
        link_selector="a.result__a, h2 a",
        desc_selectors=[".result__snippet, .snippet"],
        title=title, href=href, desc=desc, has_link=has_link,
    )


class TestDuckDuckGoUrl:
    def setup_method(self):
        self.scraper = DuckDuckGoSearchScraper(MagicMock())

    def test_url_uses_html_endpoint(self):
        url = self.scraper.build_search_url("python", None)
        assert "duckduckgo.com/html/?q=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("rust async", None)
        assert "rust" in url

    def test_site_filter_injected(self):
        f = SearchFilter(site="github.com")
        url = self.scraper.build_search_url("python", f)
        assert "github.com" in url

    def test_exact_phrase_wrapped_in_quotes(self):
        f = SearchFilter(exact_phrase="machine learning")
        url = self.scraper.build_search_url("anything", f)
        assert "machine" in url and "learning" in url


class TestDuckDuckGoExtract:
    def test_returns_search_result(self):
        item = _make_ddg_item(title="DDG Hit", href="https://ddg-result.com")
        results = DuckDuckGoSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        r = results[0]
        assert r.title == "DDG Hit"
        assert r.url == "https://ddg-result.com"
        assert r.engine == "duckduckgo"
        assert r.rank == 1

    def test_rank_increments(self):
        items = [_make_ddg_item(title=f"T{i}", href=f"https://d.com/{i}") for i in range(3)]
        results = DuckDuckGoSearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 10)
        assert [r.rank for r in results] == [1, 2, 3]

    def test_max_results_respected(self):
        items = [_make_ddg_item(title=f"T{i}", href=f"https://d.com/{i}") for i in range(5)]
        results = DuckDuckGoSearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 3)
        assert len(results) == 3

    def test_skips_item_without_link(self):
        no_link = _make_ddg_item(has_link=False)
        valid = _make_ddg_item(title="Valid", href="https://d.com/v")
        results = DuckDuckGoSearchScraper(page_with_results([no_link, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1 and results[0].title == "Valid"

    def test_description_populated(self):
        item = _make_ddg_item(desc="DDG snippet text")
        results = DuckDuckGoSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "DDG snippet text"

    def test_description_none_when_absent(self):
        item = _make_ddg_item()
        results = DuckDuckGoSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description is None

    def test_double_slash_href_gets_https_prefix(self):
        """DDG HTML sometimes returns href starting with '//'."""
        item = _make_ddg_item(href="//example.com/page")
        results = DuckDuckGoSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].url == "https://example.com/page"

    def test_returns_empty_when_no_items(self):
        assert DuckDuckGoSearchScraper(page_no_results()).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# Yahoo
# ===========================================================================

def _make_yahoo_item(title="Yahoo Result", href="https://yahoo-result.com", desc=None, has_link=True):
    return make_item_with_title_el(
        link_selector="div.compTitle a",
        title_selectors=["h3.title"],
        desc_selectors=["div.compText p"],
        title=title, href=href, desc=desc, has_link=has_link,
    )


class TestYahooUrl:
    def setup_method(self):
        self.scraper = YahooSearchScraper(MagicMock())

    def test_url_uses_yahoo_search(self):
        url = self.scraper.build_search_url("python", None)
        assert "search.yahoo.com/search?p=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("AI Agent", None)
        assert "AI" in url


class TestYahooExtract:
    def test_returns_search_result(self):
        item = _make_yahoo_item(title="Yahoo Hit", href="https://yahoo-result.com")
        results = YahooSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].engine == "yahoo"
        assert results[0].title == "Yahoo Hit"

    def test_max_results_respected(self):
        items = [_make_yahoo_item(title=f"T{i}", href=f"https://y.com/{i}") for i in range(5)]
        results = YahooSearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 3)
        assert len(results) == 3

    def test_skips_item_without_link(self):
        no_link = _make_yahoo_item(has_link=False)
        valid = _make_yahoo_item(title="Valid", href="https://y.com/v")
        results = YahooSearchScraper(page_with_results([no_link, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1

    def test_description_populated(self):
        item = _make_yahoo_item(desc="Yahoo snippet")
        results = YahooSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Yahoo snippet"

    def test_returns_empty_when_no_items(self):
        assert YahooSearchScraper(page_no_results()).extract_results("kw", SearchMode.FAST, 10) == []

    def test_exception_in_item_does_not_abort(self):
        bad = MagicMock()
        bad.locator.side_effect = RuntimeError("DOM gone")
        valid = _make_yahoo_item(title="Good", href="https://y.com/good")
        results = YahooSearchScraper(page_with_results([bad, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1 and results[0].title == "Good"


# ===========================================================================
# Startpage
# ===========================================================================

class TestStartpageUrl:
    def setup_method(self):
        self.scraper = StartpageSearchScraper(MagicMock())

    def test_url_uses_startpage_domain(self):
        url = self.scraper.build_search_url("privacy", None)
        assert "startpage.com/sp/search?query=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("open source", None)
        assert "startpage.com" in url


class TestStartpageExtract:
    """
    extract_results() now uses BeautifulSoup on page.content().
    Tests supply real HTML via make_startpage_page().
    Structure: div.result > h2/h3 > a  +  optional <p> (description)
    """

    def test_returns_search_result(self):
        page = make_startpage_page([{"title": "SP Hit", "href": "https://sp-result.com"}])
        results = StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        r = results[0]
        assert r.title == "SP Hit"
        assert r.url == "https://sp-result.com"
        assert r.engine == "startpage"
        assert r.rank == 1

    def test_rank_increments(self):
        page = make_startpage_page([{"title": f"T{i}", "href": f"https://sp.com/{i}"} for i in range(3)])
        results = StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert [r.rank for r in results] == [1, 2, 3]

    def test_max_results_respected(self):
        page = make_startpage_page([{"title": f"T{i}", "href": f"https://sp.com/{i}"} for i in range(4)])
        results = StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 2)
        assert len(results) == 2

    def test_skips_item_without_link(self):
        page = make_startpage_page([
            {"no_link": True},
            {"title": "Valid", "href": "https://sp.com/v"},
        ])
        results = StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_description_populated(self):
        page = make_startpage_page([{"title": "SP Hit", "href": "https://sp.com/h", "desc": "Privacy-first snippet"}])
        results = StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Privacy-first snippet"

    def test_description_none_when_absent(self):
        page = make_startpage_page([{"title": "SP Hit", "href": "https://sp.com/h"}])
        results = StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description is None

    def test_returns_empty_when_no_items(self):
        page = make_startpage_page([])
        assert StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []

    def test_page_content_error_returns_empty(self):
        page = MagicMock()
        page.content.side_effect = RuntimeError("Page not loaded")
        assert StartpageSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# Brave
# ===========================================================================

def _make_brave_item(title="Brave Result", href="https://brave-result.com", desc=None, has_link=True):
    return make_item_with_title_el(
        link_selector="a.heading-serpresult, a[href][data-type]",
        title_selectors=[".snippet-title, span.title, h3, h2"],
        desc_selectors=[".snippet-description, .snippet-content, p"],
        title=title, href=href, desc=desc, has_link=has_link,
    )


class TestBraveUrl:
    def setup_method(self):
        self.scraper = BraveSearchScraper(MagicMock())

    def test_url_uses_brave_domain(self):
        url = self.scraper.build_search_url("python", None)
        assert "search.brave.com/search?q=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("open source", None)
        assert "brave.com" in url

    def test_site_filter_injected(self):
        f = SearchFilter(site="github.com")
        url = self.scraper.build_search_url("rust", f)
        assert "github.com" in url


class TestBraveExtract:
    def test_returns_search_result(self):
        item = _make_brave_item(title="Brave Hit", href="https://brave-result.com")
        results = BraveSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        r = results[0]
        assert r.title == "Brave Hit"
        assert r.url == "https://brave-result.com"
        assert r.engine == "brave"

    def test_max_results_respected(self):
        items = [_make_brave_item(title=f"T{i}", href=f"https://b.com/{i}") for i in range(5)]
        results = BraveSearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 3)
        assert len(results) == 3

    def test_skips_item_without_link(self):
        no_link = _make_brave_item(has_link=False)
        valid = _make_brave_item(title="Valid", href="https://b.com/v")
        results = BraveSearchScraper(page_with_results([no_link, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1

    def test_skips_hash_href(self):
        """href='#' should be skipped."""
        item = _make_brave_item(href="#anchor")
        results = BraveSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 0

    def test_description_populated(self):
        item = _make_brave_item(desc="Brave snippet")
        results = BraveSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Brave snippet"

    def test_returns_empty_when_no_items(self):
        assert BraveSearchScraper(page_no_results()).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# Ecosia
# ===========================================================================

def _make_ecosia_item(title="Ecosia Result", href="https://ecosia-result.com", desc=None, has_link=True):
    return make_item(
        link_selector="a.result__link",
        desc_selectors=['p[data-test-id="web-result-description"]'],
        title=title, href=href, desc=desc, has_link=has_link,
    )


class TestEcosiaUrl:
    def setup_method(self):
        self.scraper = EcosiaSearchScraper(MagicMock())

    def test_url_uses_ecosia_domain(self):
        url = self.scraper.build_search_url("green energy", None)
        assert "ecosia.org/search?q=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("open source", None)
        assert "ecosia.org" in url


class TestEcosiaExtract:
    def test_returns_search_result(self):
        item = _make_ecosia_item(title="Ecosia Hit", href="https://eco-result.com")
        results = EcosiaSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].engine == "ecosia"
        assert results[0].title == "Ecosia Hit"

    def test_max_results_respected(self):
        items = [_make_ecosia_item(title=f"T{i}", href=f"https://eco.com/{i}") for i in range(4)]
        results = EcosiaSearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 2)
        assert len(results) == 2

    def test_skips_item_without_link(self):
        no_link = _make_ecosia_item(has_link=False)
        valid = _make_ecosia_item(title="Valid", href="https://eco.com/v")
        results = EcosiaSearchScraper(page_with_results([no_link, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1

    def test_description_populated(self):
        item = _make_ecosia_item(desc="Ecosia snippet")
        results = EcosiaSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Ecosia snippet"

    def test_returns_empty_when_no_items(self):
        assert EcosiaSearchScraper(page_no_results()).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# Qwant
# ===========================================================================

class TestQwantUrl:
    def setup_method(self):
        self.scraper = QwantSearchScraper(MagicMock())

    def test_url_uses_qwant_domain(self):
        url = self.scraper.build_search_url("privacy", None)
        assert "qwant.com/?q=" in url

    def test_url_has_web_tab_param(self):
        url = self.scraper.build_search_url("python", None)
        assert "t=web" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("open source", None)
        assert "qwant.com" in url

    def test_uses_domcontentloaded_in_scrape_fast(self):
        """Qwant uses domcontentloaded (not networkidle) to avoid bot-signal latency."""
        page = MagicMock()
        scraper = QwantSearchScraper(page)
        with patch.object(scraper, "extract_results", return_value=[]):
            scraper.scrape_fast("python", None, 10)
        # scrape_fast calls goto twice: once for warmup, once for the search URL.
        # The last call (search URL) must use domcontentloaded.
        call_kwargs = page.goto.call_args[1]
        assert call_kwargs.get("wait_until") == "domcontentloaded"


class TestQwantExtract:
    """Qwant uses CSS-in-JS class names; tests supply real HTML via make_qwant_page()."""

    def test_returns_search_result(self):
        page = make_qwant_page([{"title": "Qwant Hit", "href": "https://qwant-result.com"}])
        results = QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        r = results[0]
        assert r.title == "Qwant Hit"
        assert r.url == "https://qwant-result.com"
        assert r.engine == "qwant"
        assert r.rank == 1

    def test_rank_increments(self):
        page = make_qwant_page([{"title": f"T{i}", "href": f"https://q.com/{i}"} for i in range(3)])
        results = QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert [r.rank for r in results] == [1, 2, 3]

    def test_max_results_respected(self):
        page = make_qwant_page([{"title": f"T{i}", "href": f"https://q.com/{i}"} for i in range(5)])
        results = QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 3)
        assert len(results) == 3

    def test_skips_item_without_domain_attr(self):
        page = make_qwant_page([
            {"no_href": True, "title": "No Link"},
            {"title": "Valid", "href": "https://q.com/v"},
        ])
        results = QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_description_populated(self):
        page = make_qwant_page([{"title": "Qwant Hit", "href": "https://q.com/h", "desc": "Qwant snippet"}])
        results = QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Qwant snippet"

    def test_description_none_when_absent(self):
        page = make_qwant_page([{"title": "Qwant Hit", "href": "https://q.com/h"}])
        results = QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description is None

    def test_returns_empty_when_no_items(self):
        page = make_qwant_page([])
        assert QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []

    def test_page_content_error_returns_empty(self):
        page = MagicMock()
        page.content.side_effect = RuntimeError("Page not loaded")
        assert QwantSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# WolframAlpha
# ===========================================================================

class TestWolframAlphaUrl:
    def setup_method(self):
        self.scraper = WolframAlphaSearchScraper(MagicMock())

    def test_url_uses_wolframalpha_domain(self):
        url = self.scraper.build_search_url("integrate x^2", None)
        assert "wolframalpha.com/input?i=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("100 USD to CNY", None)
        assert "wolframalpha.com" in url

    def test_uses_networkidle_in_scrape_fast(self):
        page = MagicMock()
        scraper = WolframAlphaSearchScraper(page)
        with patch.object(scraper, "extract_results", return_value=[]):
            scraper.scrape_fast("integrate x^2", None, 5)
        call_kwargs = page.goto.call_args[1]
        assert call_kwargs.get("wait_until") == "networkidle"


class TestWolframAlphaExtract:
    """WolframAlpha merges ALL pods into a single SearchResult.
    Tests supply real HTML via make_wa_page()."""

    def test_all_pods_merged_into_one_result(self):
        """Multiple pods → exactly one SearchResult."""
        pods = [
            {"title": "Input interpretation:", "content": "convert $10 to CNY"},
            {"title": "Result:", "content": "¥68.21"},
            {"title": "History:", "content": "Low | 60\nHigh | 75"},
        ]
        results = WolframAlphaSearchScraper(make_wa_page(pods)).extract_results(
            "10 USD to CNY", SearchMode.FAST, 10
        )
        assert len(results) == 1

    def test_result_title_is_keyword(self):
        pods = [{"title": "Result:", "content": "¥68.21"}]
        results = WolframAlphaSearchScraper(make_wa_page(pods)).extract_results(
            "10 USD to CNY", SearchMode.FAST, 10
        )
        assert results[0].title == "10 USD to CNY"
        assert results[0].engine == "wolframalpha"
        assert results[0].keyword == "10 USD to CNY"
        assert results[0].rank == 1

    def test_description_contains_all_pod_contents(self):
        pods = [
            {"title": "Input:", "content": "integrate x^2"},
            {"title": "Result:", "content": "x^3 / 3 + C"},
            {"title": "Plot:", "content": "parabola image"},
        ]
        results = WolframAlphaSearchScraper(make_wa_page(pods)).extract_results(
            "integrate x^2", SearchMode.FAST, 10
        )
        desc = results[0].description
        assert "Input:" in desc
        assert "integrate x^2" in desc
        assert "Result:" in desc
        assert "x^3 / 3 + C" in desc
        assert "Plot:" in desc

    def test_url_is_query_url(self):
        page = make_wa_page([{"title": "Result:", "content": "¥68.21"}])
        results = WolframAlphaSearchScraper(page).extract_results("100 USD to CNY", SearchMode.FAST, 10)
        assert "wolframalpha.com/input" in results[0].url
        assert "100" in results[0].url or "USD" in results[0].url

    def test_pods_separated_by_blank_line(self):
        pods = [
            {"title": "A:", "content": "alpha"},
            {"title": "B:", "content": "beta"},
        ]
        results = WolframAlphaSearchScraper(make_wa_page(pods)).extract_results("q", SearchMode.FAST, 10)
        assert "\n\n" in results[0].description

    def test_title_only_pod_included_without_content(self):
        """A pod with no <img> is still recorded as a title-only line."""
        pods = [
            {"title": "Section header", "content": None},
            {"title": "Result:", "content": "42"},
        ]
        results = WolframAlphaSearchScraper(make_wa_page(pods)).extract_results("q", SearchMode.FAST, 10)
        assert len(results) == 1
        assert "Section header" in results[0].description

    def test_skips_pod_with_empty_title(self):
        pods = [
            {"title": "", "content": "orphan content"},
            {"title": "Valid:", "content": "answer"},
        ]
        results = WolframAlphaSearchScraper(make_wa_page(pods)).extract_results("q", SearchMode.FAST, 10)
        assert "Valid:" in results[0].description
        assert "orphan content" not in results[0].description

    def test_multiline_alt_text_preserved(self):
        content = "Low | 681.58\nHigh | 731.34\nAvg | 708.18"
        page = make_wa_page([{"title": "History:", "content": content}])
        results = WolframAlphaSearchScraper(page).extract_results("q", SearchMode.FAST, 10)
        assert "Low" in results[0].description
        assert "High" in results[0].description
        assert "Avg" in results[0].description

    def test_description_truncated_at_3000_chars(self):
        pods = [{"title": f"Pod{i}:", "content": "x" * 400} for i in range(10)]
        results = WolframAlphaSearchScraper(make_wa_page(pods)).extract_results("q", SearchMode.FAST, 10)
        assert len(results[0].description) == 3000

    def test_returns_empty_when_no_pods(self):
        page = MagicMock()
        page.content.return_value = "<html><body></body></html>"
        assert WolframAlphaSearchScraper(page).extract_results("q", SearchMode.FAST, 10) == []

    def test_page_content_error_returns_empty(self):
        page = MagicMock()
        page.content.side_effect = RuntimeError("Page not loaded")
        assert WolframAlphaSearchScraper(page).extract_results("q", SearchMode.FAST, 10) == []
