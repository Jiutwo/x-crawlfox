"""
Tests for search engine scrapers.

Coverage:
  - BaseSearchScraper.build_keyword_with_operators (pure logic)
  - BaseSearchScraper._find_search_input / scrape() dispatch / exception guard
  - BaiduSearchScraper.build_search_url + extract_results + scrape modes
  - GoogleSearchScraper.build_search_url + extract_results
  - BingSearchScraper.build_search_url + extract_results

All Playwright page interactions are replaced with MagicMock.
"""
from unittest.mock import MagicMock, patch

from x_crawlfox.models.search_schema import (
    SearchMode,
    TimeRange,
    SearchFilter,
    SearchResult,
)
from x_crawlfox.scrapers.search.engines.baidu import BaiduSearchScraper
from x_crawlfox.scrapers.search.engines.google import GoogleSearchScraper
from x_crawlfox.scrapers.search.engines.bing import BingSearchScraper


# ---------------------------------------------------------------------------
# Helpers — build mock DOM elements for each engine
# ---------------------------------------------------------------------------

def _make_baidu_container(title="Baidu Result", href="https://baidu-link.com", desc=None, has_link=True):
    """Mock a Baidu .c-container element."""
    link = MagicMock()
    link.count.return_value = 1 if has_link else 0
    link.inner_text.return_value = title
    link.get_attribute.return_value = href

    desc_el = MagicMock()
    desc_el.count.return_value = 1 if desc else 0
    desc_el.inner_text.return_value = desc or ""

    empty = MagicMock()
    empty.count.return_value = 0

    def _locator(selector):
        m = MagicMock()
        if selector == "h3 a":
            m.first = link
        elif selector in (".c-abstract", ".c-font-normal", ".c-span-last"):
            m.first = desc_el
        else:
            m.first = empty
        return m

    container = MagicMock()
    container.locator.side_effect = _locator
    return container


def _make_google_h3(title="Google Result", href="https://google-link.com", desc=None, has_link=True):
    """Mock a Google h3 element as consumed by the extractor.

    The extractor walks the DOM via XPath ancestors, so the h3 mock must
    respond to:
      h3.inner_text()                              → title
      h3.locator("xpath=ancestor::a[...]").first   → link element
      h3.locator("xpath=ancestor::div[4]").first   → card element
    and the card mock must respond to:
      card.count()                                 → 1
      card.locator(".VwiC3b" / ...).first          → description element
    """
    # -- link element --
    link = MagicMock()
    link.count.return_value = 1 if has_link else 0
    link.get_attribute.return_value = href

    # -- description element inside the card --
    desc_el = MagicMock()
    desc_el.count.return_value = 1 if desc else 0
    desc_el.inner_text.return_value = desc or ""

    empty = MagicMock()
    empty.count.return_value = 0

    # -- card element --
    card = MagicMock()
    card.count.return_value = 1

    def _card_locator(selector):
        m = MagicMock()
        if selector in (".VwiC3b", "[data-sncf='1']", ".IsZvec", "span[style]"):
            m.first = desc_el
        else:
            m.first = empty
        return m

    card.locator.side_effect = _card_locator

    # -- h3 element --
    h3 = MagicMock()
    h3.inner_text.return_value = title

    def _h3_locator(selector):
        m = MagicMock()
        if "ancestor::a" in selector or "..//a" in selector:
            m.first = link
        elif "ancestor::div" in selector:
            m.first = card
        else:
            m.first = empty
        return m

    h3.locator.side_effect = _h3_locator
    return h3


def _make_bing_block(title="Bing Result", href="https://bing-link.com", desc=None, has_link=True):
    """Mock a Bing li.b_algo element."""
    link = MagicMock()
    link.count.return_value = 1 if has_link else 0
    link.inner_text.return_value = title
    link.get_attribute.return_value = href

    desc_el = MagicMock()
    desc_el.count.return_value = 1 if desc else 0
    desc_el.inner_text.return_value = desc or ""

    def _locator(selector):
        m = MagicMock()
        if selector == "h2 a":
            m.first = link
        elif selector == "p":
            m.first = desc_el
        return m

    block = MagicMock()
    block.locator.side_effect = _locator
    return block


def _page_with_results(result_list):
    """Return a mock page whose locator(...).all() yields result_list."""
    page = MagicMock()
    page.locator.return_value.all.return_value = result_list
    return page


def _page_with_visible_input():
    """Return a mock page whose search input is found and visible."""
    page = MagicMock()
    mock_input = MagicMock()
    mock_input.count.return_value = 1
    mock_input.wait_for.return_value = None   # no exception → visible
    page.locator.return_value.first = mock_input
    return page


def _page_with_no_input():
    """Return a mock page where no search input is found."""
    page = MagicMock()
    page.locator.return_value.first.count.return_value = 0
    return page


# ===========================================================================
# 1. build_keyword_with_operators  (BaseSearchScraper — pure logic)
# ===========================================================================

class TestBuildKeywordWithOperators:
    def setup_method(self):
        self.scraper = BaiduSearchScraper(MagicMock())

    def test_no_filter_returns_keyword_unchanged(self):
        assert self.scraper.build_keyword_with_operators("python", None) == "python"

    def test_empty_filter_returns_keyword_unchanged(self):
        f = SearchFilter()
        assert self.scraper.build_keyword_with_operators("python", f) == "python"

    def test_site_filter_appended(self):
        f = SearchFilter(site="github.com")
        result = self.scraper.build_keyword_with_operators("python", f)
        assert "python" in result
        assert "site:github.com" in result

    def test_filetype_filter_appended(self):
        f = SearchFilter(filetype="pdf")
        result = self.scraper.build_keyword_with_operators("report", f)
        assert "report" in result
        assert "filetype:pdf" in result

    def test_exact_phrase_replaces_keyword(self):
        f = SearchFilter(exact_phrase="machine learning")
        result = self.scraper.build_keyword_with_operators("anything", f)
        assert '"machine learning"' in result
        # keyword is replaced, not appended
        assert "anything" not in result

    def test_exclude_terms_prepended_with_dash(self):
        f = SearchFilter(exclude_terms=["spam", "ads"])
        result = self.scraper.build_keyword_with_operators("news", f)
        assert "-spam" in result
        assert "-ads" in result

    def test_combined_filters(self):
        f = SearchFilter(site="github.com", filetype="pdf", exclude_terms=["draft"])
        result = self.scraper.build_keyword_with_operators("report", f)
        assert "report" in result
        assert "site:github.com" in result
        assert "filetype:pdf" in result
        assert "-draft" in result


# ===========================================================================
# 2. BaseSearchScraper dispatch & error handling
# ===========================================================================

class TestBaseScraperDispatch:
    """Uses BaiduSearchScraper as a concrete stand-in for BaseSearchScraper."""

    def test_scrape_fast_mode_calls_scrape_fast(self):
        scraper = BaiduSearchScraper(MagicMock())
        with patch.object(scraper, "scrape_fast", return_value=[]) as mock_fast:
            scraper.scrape("kw", mode=SearchMode.FAST)
        mock_fast.assert_called_once_with("kw", None, 10)

    def test_scrape_simulate_mode_calls_scrape_simulate(self):
        scraper = BaiduSearchScraper(MagicMock())
        with patch.object(scraper, "scrape_simulate", return_value=[]) as mock_sim:
            scraper.scrape("kw", mode=SearchMode.SIMULATE)
        mock_sim.assert_called_once_with("kw", None, 10)

    def test_scrape_default_mode_is_simulate(self):
        scraper = BaiduSearchScraper(MagicMock())
        with patch.object(scraper, "scrape_simulate", return_value=[]) as mock_sim:
            scraper.scrape("kw")
        mock_sim.assert_called_once()

    def test_scrape_exception_returns_empty_list(self):
        scraper = BaiduSearchScraper(MagicMock())
        with patch.object(scraper, "scrape_fast", side_effect=RuntimeError("boom")):
            results = scraper.scrape("kw", mode=SearchMode.FAST)
        assert results == []

    def test_find_search_input_returns_element_when_visible(self):
        page = _page_with_visible_input()
        scraper = BaiduSearchScraper(page)
        elem = scraper._find_search_input()
        assert elem is not None

    def test_find_search_input_returns_none_when_not_found(self):
        page = _page_with_no_input()
        scraper = BaiduSearchScraper(page)
        elem = scraper._find_search_input()
        assert elem is None

    def test_find_search_input_skips_selector_on_wait_for_exception(self):
        """If wait_for raises, try the next selector."""
        page = MagicMock()
        bad_input = MagicMock()
        bad_input.count.return_value = 1
        bad_input.wait_for.side_effect = Exception("timeout")

        good_input = MagicMock()
        good_input.count.return_value = 1
        good_input.wait_for.return_value = None

        call_count = [0]

        def _locator(_):
            m = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                m.first = bad_input
            else:
                m.first = good_input
            return m

        page.locator.side_effect = _locator
        scraper = BaiduSearchScraper(page)
        elem = scraper._find_search_input()
        assert elem is good_input


# ===========================================================================
# 3. BaiduSearchScraper
# ===========================================================================

class TestBaiduBuildSearchUrl:
    def setup_method(self):
        self.scraper = BaiduSearchScraper(MagicMock())

    def test_basic_url(self):
        url = self.scraper.build_search_url("python", None)
        assert url.startswith("https://www.baidu.com/s?wd=")
        assert "python" in url

    def test_keyword_is_url_encoded(self):
        url = self.scraper.build_search_url("AI Agent", None)
        assert "AI+Agent" in url or "AI%20Agent" in url

    def test_time_range_adds_tbs_param(self):
        f = SearchFilter(time_range=TimeRange.WEEK)
        url = self.scraper.build_search_url("news", f)
        assert "tbs=qdr:w" in url

    def test_all_time_ranges_produce_distinct_params(self):
        params = set()
        for tr in TimeRange:
            f = SearchFilter(time_range=tr)
            url = self.scraper.build_search_url("x", f)
            tbs = [p for p in url.split("&") if p.startswith("tbs=")]
            if tbs:
                params.add(tbs[0])
        # Baidu maps 5 time ranges → 5 distinct tbs values
        assert len(params) == 5

    def test_site_filter_injected_in_keyword(self):
        f = SearchFilter(site="github.com")
        url = self.scraper.build_search_url("python", f)
        assert "site%3Agithub.com" in url or "site:github.com" in url


class TestBaiduExtractResults:
    def test_returns_search_results_with_correct_fields(self):
        container = _make_baidu_container(title="Hello Baidu", href="https://b.com")
        page = _page_with_results([container])
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, SearchResult)
        assert r.title == "Hello Baidu"
        assert r.url == "https://b.com"
        assert r.engine == "baidu"
        assert r.keyword == "kw"
        assert r.mode == SearchMode.FAST
        assert r.rank == 1

    def test_rank_increments_per_result(self):
        containers = [_make_baidu_container(title=f"T{i}", href=f"https://b.com/{i}") for i in range(3)]
        page = _page_with_results(containers)
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert [r.rank for r in results] == [1, 2, 3]

    def test_max_results_is_respected(self):
        containers = [_make_baidu_container(title=f"T{i}", href=f"https://b.com/{i}") for i in range(5)]
        page = _page_with_results(containers)
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, max_results=3)

        assert len(results) == 3

    def test_skips_item_with_no_link_element(self):
        no_link = _make_baidu_container(has_link=False)
        valid = _make_baidu_container(title="Valid", href="https://b.com")
        page = _page_with_results([no_link, valid])
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_skips_item_with_empty_title(self):
        empty_title = _make_baidu_container(title="", href="https://b.com")
        valid = _make_baidu_container(title="Real Title", href="https://b.com/2")
        page = _page_with_results([empty_title, valid])
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Real Title"

    def test_skips_item_with_no_href(self):
        no_href = _make_baidu_container(title="Title", href=None)
        valid = _make_baidu_container(title="Valid", href="https://b.com")
        page = _page_with_results([no_href, valid])
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert len(results) == 1

    def test_description_populated_when_present(self):
        container = _make_baidu_container(title="T", href="https://b.com", desc="A snippet.")
        page = _page_with_results([container])
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert results[0].description == "A snippet."

    def test_description_is_none_when_absent(self):
        container = _make_baidu_container(title="T", href="https://b.com")
        page = _page_with_results([container])
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert results[0].description is None

    def test_returns_empty_when_no_containers(self):
        page = _page_with_results([])
        scraper = BaiduSearchScraper(page)
        assert scraper.extract_results("kw", SearchMode.FAST, 10) == []

    def test_continues_after_single_item_exception(self):
        """An exception in one container should not abort the whole loop."""
        bad = MagicMock()
        bad.locator.side_effect = RuntimeError("DOM gone")
        good = _make_baidu_container(title="Good", href="https://b.com")
        page = _page_with_results([bad, good])
        scraper = BaiduSearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Good"


class TestBaiduScrapeModes:
    def test_scrape_fast_navigates_to_search_url_and_calls_extract(self):
        page = MagicMock()
        scraper = BaiduSearchScraper(page)

        with patch.object(scraper, "extract_results", return_value=[]) as mock_extract:
            scraper.scrape_fast("python", None, 10)

        url_arg = page.goto.call_args[0][0]
        assert "baidu.com/s" in url_arg
        assert "python" in url_arg
        page.wait_for_selector.assert_called_once_with(".c-container", timeout=15000)
        mock_extract.assert_called_once_with("python", SearchMode.FAST, 10)

    def test_scrape_simulate_types_keyword_and_presses_enter(self):
        page = _page_with_visible_input()
        scraper = BaiduSearchScraper(page)

        with patch.object(scraper, "extract_results", return_value=[]):
            scraper.scrape_simulate("python", None, 10)

        page.goto.assert_called_once_with("https://www.baidu.com", wait_until="domcontentloaded", timeout=60000)
        typed = page.keyboard.type.call_args[0][0]
        assert typed == "python"
        page.keyboard.press.assert_called_once_with("Enter")

    def test_scrape_simulate_falls_back_to_fast_when_no_input(self):
        page = _page_with_no_input()
        scraper = BaiduSearchScraper(page)

        with patch.object(scraper, "scrape_fast", return_value=[]) as mock_fast:
            scraper.scrape_simulate("python", None, 10)

        mock_fast.assert_called_once_with("python", None, 10)

    def test_scrape_simulate_applies_filter_operators_to_typed_text(self):
        page = _page_with_visible_input()
        scraper = BaiduSearchScraper(page)
        f = SearchFilter(site="github.com")

        with patch.object(scraper, "extract_results", return_value=[]):
            scraper.scrape_simulate("python", f, 10)

        typed = page.keyboard.type.call_args[0][0]
        assert "site:github.com" in typed


# ===========================================================================
# 4. GoogleSearchScraper — CAPTCHA handling
# ===========================================================================

class TestGoogleCaptchaHandling:
    def test_wait_if_captcha_returns_true_on_normal_url(self):
        page = MagicMock()
        type(page).url = property(lambda self: "https://www.google.com/search?q=test")
        scraper = GoogleSearchScraper(page)
        assert scraper._wait_if_captcha() is True

    def test_wait_if_captcha_waits_and_returns_true_when_resolved(self):
        page = MagicMock()
        type(page).url = property(lambda self: "https://www.google.com/sorry/index?continue=...")
        page.wait_for_url.return_value = None  # no exception = resolved

        scraper = GoogleSearchScraper(page)
        result = scraper._wait_if_captcha()

        page.wait_for_url.assert_called_once_with("**/search**", timeout=90_000)
        assert result is True

    def test_wait_if_captcha_returns_false_when_timeout(self):
        page = MagicMock()
        type(page).url = property(lambda self: "https://www.google.com/sorry/index?continue=...")
        page.wait_for_url.side_effect = Exception("timeout")

        scraper = GoogleSearchScraper(page)
        result = scraper._wait_if_captcha()

        assert result is False

    def test_scrape_fast_aborts_on_captcha(self):
        page = MagicMock()
        scraper = GoogleSearchScraper(page)

        with patch.object(scraper, "_wait_if_captcha", return_value=False):
            results = scraper.scrape_fast("kw", None, 10)

        assert results == []

    def test_scrape_simulate_aborts_on_captcha(self):
        page = _page_with_visible_input()
        scraper = GoogleSearchScraper(page)

        with patch.object(scraper, "_wait_if_captcha", return_value=False):
            results = scraper.scrape_simulate("kw", None, 10)

        assert results == []

    def test_scrape_simulate_proceeds_when_no_captcha(self):
        page = _page_with_visible_input()
        scraper = GoogleSearchScraper(page)

        with patch.object(scraper, "_wait_if_captcha", return_value=True), \
             patch.object(scraper, "extract_results", return_value=[]) as mock_extract:
            scraper.scrape_simulate("kw", None, 10)

        mock_extract.assert_called_once_with("kw", SearchMode.SIMULATE, 10)


# ===========================================================================
# 5. GoogleSearchScraper — URL building
# ===========================================================================

class TestGoogleBuildSearchUrl:
    def setup_method(self):
        self.scraper = GoogleSearchScraper(MagicMock())

    def test_basic_url(self):
        url = self.scraper.build_search_url("flask", None)
        assert "google.com/search?q=" in url
        assert "flask" in url

    def test_time_range_adds_tbs_param(self):
        f = SearchFilter(time_range=TimeRange.DAY)
        url = self.scraper.build_search_url("news", f)
        assert "tbs=qdr:d" in url

    def test_language_filter_adds_lr_param(self):
        f = SearchFilter(language="zh-CN")
        url = self.scraper.build_search_url("news", f)
        assert "lr=lang_zh-CN" in url

    def test_site_filter_injected_in_keyword(self):
        f = SearchFilter(site="stackoverflow.com")
        url = self.scraper.build_search_url("python", f)
        assert "stackoverflow.com" in url


class TestGoogleExtractResults:
    """
    The extractor now iterates h3 elements (page.locator('#rso h3, #search h3').all())
    and walks up via XPath ancestors for the link and result card.
    Mocks are built with _make_google_h3().
    """

    def test_returns_correct_search_result(self):
        h3 = _make_google_h3(title="Flask Docs", href="https://flask.palletsprojects.com")
        page = _page_with_results([h3])
        scraper = GoogleSearchScraper(page)

        results = scraper.extract_results("flask", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Flask Docs"
        assert results[0].url == "https://flask.palletsprojects.com"
        assert results[0].engine == "google"
        assert results[0].rank == 1

    def test_max_results_respected(self):
        h3s = [_make_google_h3(title=f"R{i}", href=f"https://g.com/{i}") for i in range(5)]
        page = _page_with_results(h3s)
        scraper = GoogleSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, max_results=2)

        assert len(results) == 2

    def test_skips_h3_with_empty_title(self):
        """h3 elements with empty inner_text are skipped."""
        empty_title = _make_google_h3(title="", href="https://g.com")
        valid = _make_google_h3(title="Valid", href="https://g.com/2")
        page = _page_with_results([empty_title, valid])
        scraper = GoogleSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_skips_h3_with_no_link(self):
        """h3 elements where no ancestor <a> is found are skipped."""
        no_link = _make_google_h3(title="No Link", has_link=False)
        valid = _make_google_h3(title="Has Link", href="https://g.com")
        page = _page_with_results([no_link, valid])
        scraper = GoogleSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Has Link"

    def test_skips_internal_google_search_links(self):
        internal = _make_google_h3(title="Internal", href="/search?q=something")
        valid = _make_google_h3(title="External", href="https://real.com")
        page = _page_with_results([internal, valid])
        scraper = GoogleSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "External"

    def test_description_captured(self):
        h3 = _make_google_h3(title="Result", href="https://g.com", desc="Helpful snippet")
        page = _page_with_results([h3])
        scraper = GoogleSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert results[0].description == "Helpful snippet"

    def test_description_none_when_absent(self):
        h3 = _make_google_h3(title="T", href="https://g.com")
        page = _page_with_results([h3])
        scraper = GoogleSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert results[0].description is None

    def test_returns_empty_on_no_h3s(self):
        page = _page_with_results([])
        scraper = GoogleSearchScraper(page)
        assert scraper.extract_results("q", SearchMode.FAST, 10) == []


# ===========================================================================
# 5. BingSearchScraper
# ===========================================================================

class TestBingBuildSearchUrl:
    def setup_method(self):
        self.scraper = BingSearchScraper(MagicMock())

    def test_basic_url(self):
        url = self.scraper.build_search_url("rust", None)
        assert "bing.com/search?q=" in url
        assert "rust" in url

    def test_day_filter_adds_filters_param(self):
        f = SearchFilter(time_range=TimeRange.DAY)
        url = self.scraper.build_search_url("news", f)
        assert "filters=" in url

    def test_week_filter_differs_from_day(self):
        url_day = self.scraper.build_search_url("x", SearchFilter(time_range=TimeRange.DAY))
        url_week = self.scraper.build_search_url("x", SearchFilter(time_range=TimeRange.WEEK))
        assert url_day != url_week

    def test_unsupported_time_range_adds_no_filter(self):
        # Bing doesn't map HOUR — should produce a URL without filters param
        f = SearchFilter(time_range=TimeRange.HOUR)
        url = self.scraper.build_search_url("x", f)
        assert "filters=" not in url


class TestBingExtractResults:
    def test_returns_correct_search_result(self):
        block = _make_bing_block(title="Rust Lang", href="https://rust-lang.org")
        page = _page_with_results([block])
        scraper = BingSearchScraper(page)

        results = scraper.extract_results("rust", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Rust Lang"
        assert results[0].url == "https://rust-lang.org"
        assert results[0].engine == "bing"
        assert results[0].rank == 1

    def test_max_results_respected(self):
        blocks = [_make_bing_block(title=f"R{i}", href=f"https://b.com/{i}") for i in range(6)]
        page = _page_with_results(blocks)
        scraper = BingSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, max_results=4)

        assert len(results) == 4

    def test_skips_block_with_no_link(self):
        no_link = _make_bing_block(has_link=False)
        valid = _make_bing_block(title="Valid", href="https://b.com")
        page = _page_with_results([no_link, valid])
        scraper = BingSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_description_captured(self):
        block = _make_bing_block(title="T", href="https://b.com", desc="A bing snippet.")
        page = _page_with_results([block])
        scraper = BingSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert results[0].description == "A bing snippet."

    def test_description_none_when_absent(self):
        block = _make_bing_block(title="T", href="https://b.com")
        page = _page_with_results([block])
        scraper = BingSearchScraper(page)

        results = scraper.extract_results("q", SearchMode.FAST, 10)

        assert results[0].description is None

    def test_returns_empty_on_no_blocks(self):
        page = _page_with_results([])
        scraper = BingSearchScraper(page)
        assert scraper.extract_results("q", SearchMode.FAST, 10) == []
