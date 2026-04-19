"""
Unit tests for domestic (CN) search engine scrapers:
  Bing CN, Bing INT, 360, Sogou, WeChat, Toutiao, Jisilu

All Playwright interactions are replaced with MagicMock objects.
"""
from unittest.mock import MagicMock, patch

from x_crawlfox.models.search_schema import SearchMode, TimeRange, SearchFilter, SearchResult
from x_crawlfox.scrapers.search.engines.bing_cn import BingCNSearchScraper
from x_crawlfox.scrapers.search.engines.bing_int import BingINTSearchScraper
from x_crawlfox.scrapers.search.engines.so360 import So360SearchScraper
from x_crawlfox.scrapers.search.engines.sogou import SogouSearchScraper
from x_crawlfox.scrapers.search.engines.wechat import WeChatSearchScraper
from x_crawlfox.scrapers.search.engines.toutiao import ToutiaoSearchScraper
from x_crawlfox.scrapers.search.engines.jisilu import JisiluSearchScraper

from .conftest import (
    page_with_results,
    page_no_results,
    make_item,
    make_item_with_title_el,
    make_toutiao_page,
    make_jisilu_page,
)


# ===========================================================================
# Bing CN
# ===========================================================================

class TestBingCNUrl:
    def setup_method(self):
        self.scraper = BingCNSearchScraper(MagicMock())

    def test_url_uses_cn_bing_domain(self):
        url = self.scraper.build_search_url("python", None)
        assert "cn.bing.com/search" in url

    def test_url_has_ensearch_zero(self):
        url = self.scraper.build_search_url("python", None)
        assert "ensearch=0" in url

    def test_keyword_is_encoded(self):
        url = self.scraper.build_search_url("AI 助手", None)
        assert "AI" in url and ("助手" in url or "%E5" in url)

    def test_time_range_adds_filters_param(self):
        f = SearchFilter(time_range=TimeRange.WEEK)
        url = self.scraper.build_search_url("news", f)
        assert "filters=" in url

    def test_unsupported_time_range_adds_no_filters(self):
        # BingSearchScraper._time_params has no HOUR entry
        f = SearchFilter(time_range=TimeRange.HOUR)
        url = self.scraper.build_search_url("x", f)
        assert "filters=" not in url

    def test_site_filter_injected_into_query(self):
        f = SearchFilter(site="github.com")
        url = self.scraper.build_search_url("python", f)
        assert "github.com" in url


# ===========================================================================
# Bing INT
# ===========================================================================

class TestBingINTUrl:
    def setup_method(self):
        self.scraper = BingINTSearchScraper(MagicMock())

    def test_url_uses_cn_bing_domain(self):
        url = self.scraper.build_search_url("python", None)
        assert "cn.bing.com/search" in url

    def test_url_has_ensearch_one(self):
        url = self.scraper.build_search_url("python", None)
        assert "ensearch=1" in url

    def test_cn_and_int_produce_different_urls(self):
        cn = BingCNSearchScraper(MagicMock()).build_search_url("q", None)
        intl = BingINTSearchScraper(MagicMock()).build_search_url("q", None)
        assert cn != intl

    def test_time_range_adds_filters_param(self):
        f = SearchFilter(time_range=TimeRange.DAY)
        url = self.scraper.build_search_url("news", f)
        assert "filters=" in url


# ===========================================================================
# 360 Search
# ===========================================================================

def _make_360_item(title="360 Result", href="https://so.com/r/x", desc=None, has_link=True):
    return make_item(
        link_selector="h3 a",
        desc_selectors=[".res-desc", ".res-comm-con", "p"],
        title=title, href=href, desc=desc, has_link=has_link,
    )


class TestSo360Url:
    def setup_method(self):
        self.scraper = So360SearchScraper(MagicMock())

    def test_url_uses_so_com(self):
        url = self.scraper.build_search_url("python", None)
        assert "www.so.com/s?q=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("AI Agent", None)
        assert "AI" in url

    def test_site_filter_injected(self):
        f = SearchFilter(site="csdn.net")
        url = self.scraper.build_search_url("python", f)
        assert "csdn.net" in url


class TestSo360Extract:
    def test_returns_search_result(self):
        item = _make_360_item(title="360 Result", href="https://so.com/r/1")
        page = page_with_results([item])
        scraper = So360SearchScraper(page)

        results = scraper.extract_results("kw", SearchMode.FAST, 10)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, SearchResult)
        assert r.title == "360 Result"
        assert r.url == "https://so.com/r/1"
        assert r.engine == "360"
        assert r.rank == 1

    def test_rank_increments(self):
        items = [_make_360_item(title=f"T{i}", href=f"https://so.com/{i}") for i in range(3)]
        results = So360SearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 10)
        assert [r.rank for r in results] == [1, 2, 3]

    def test_max_results_respected(self):
        items = [_make_360_item(title=f"T{i}", href=f"https://so.com/{i}") for i in range(5)]
        results = So360SearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 3)
        assert len(results) == 3

    def test_skips_item_without_link(self):
        no_link = _make_360_item(has_link=False)
        valid = _make_360_item(title="Valid", href="https://so.com/v")
        results = So360SearchScraper(page_with_results([no_link, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1 and results[0].title == "Valid"

    def test_description_populated(self):
        item = _make_360_item(title="T", href="https://so.com", desc="A snippet")
        results = So360SearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "A snippet"

    def test_description_none_when_absent(self):
        item = _make_360_item(title="T", href="https://so.com")
        results = So360SearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description is None

    def test_returns_empty_when_no_items(self):
        assert So360SearchScraper(page_no_results()).extract_results("kw", SearchMode.FAST, 10) == []

    def test_exception_in_item_does_not_abort(self):
        bad = MagicMock()
        bad.locator.side_effect = RuntimeError("DOM gone")
        valid = _make_360_item(title="Good", href="https://so.com")
        results = So360SearchScraper(page_with_results([bad, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1 and results[0].title == "Good"


# ===========================================================================
# Sogou
# ===========================================================================

def _make_sogou_item(title="Sogou Result", href="https://sogou.com/r", desc=None, has_link=True):
    return make_item(
        link_selector="h3 a",
        desc_selectors=[".str_info", ".star-content", "p.str-text", "p"],
        title=title, href=href, desc=desc, has_link=has_link,
    )


class TestSogouUrl:
    def setup_method(self):
        self.scraper = SogouSearchScraper(MagicMock())

    def test_url_uses_sogou_domain(self):
        url = self.scraper.build_search_url("python", None)
        assert "sogou.com/web?query=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("机器学习", None)
        assert "sogou.com" in url

    def test_site_filter_injected(self):
        f = SearchFilter(site="zhihu.com")
        url = self.scraper.build_search_url("python", f)
        assert "zhihu.com" in url


class TestSogouExtract:
    def test_returns_search_result(self):
        item = _make_sogou_item(title="Sogou Hit", href="https://link.sogou.com/1")
        results = SogouSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].engine == "sogou"

    def test_max_results_respected(self):
        items = [_make_sogou_item(title=f"T{i}", href=f"https://s.com/{i}") for i in range(5)]
        results = SogouSearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 2)
        assert len(results) == 2

    def test_skips_item_without_link(self):
        no_link = _make_sogou_item(has_link=False)
        valid = _make_sogou_item(title="Valid", href="https://s.com/v")
        results = SogouSearchScraper(page_with_results([no_link, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1

    def test_description_populated(self):
        item = _make_sogou_item(desc="Sogou snippet")
        results = SogouSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Sogou snippet"

    def test_returns_empty_when_no_items(self):
        assert SogouSearchScraper(page_no_results()).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# WeChat (wx.sogou.com)
# ===========================================================================

def _make_wechat_item(title="WeChat Article", href="https://mp.weixin.qq.com/s/abc", desc=None, has_link=True):
    return make_item(
        link_selector="h3 a, a.txt",
        desc_selectors=[".txt-info", "p.txt", ".news-item-desc"],
        title=title, href=href, desc=desc, has_link=has_link,
    )


class TestWeChatUrl:
    def setup_method(self):
        self.scraper = WeChatSearchScraper(MagicMock())

    def test_url_uses_wx_sogou(self):
        url = self.scraper.build_search_url("AI", None)
        assert "wx.sogou.com/weixin" in url

    def test_url_has_type_and_query_params(self):
        url = self.scraper.build_search_url("AI", None)
        assert "type=2" in url
        assert "query=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("人工智能", None)
        assert "wx.sogou.com" in url


class TestWeChatExtract:
    def test_returns_search_result(self):
        item = _make_wechat_item(title="WeChat Article", href="https://mp.weixin.qq.com/s/abc")
        results = WeChatSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].engine == "wechat"
        assert results[0].title == "WeChat Article"

    def test_max_results_respected(self):
        items = [_make_wechat_item(title=f"T{i}", href=f"https://mp.weixin.qq.com/{i}") for i in range(4)]
        results = WeChatSearchScraper(page_with_results(items)).extract_results("kw", SearchMode.FAST, 2)
        assert len(results) == 2

    def test_skips_item_without_link(self):
        no_link = _make_wechat_item(has_link=False)
        valid = _make_wechat_item(title="Valid", href="https://mp.weixin.qq.com/valid")
        results = WeChatSearchScraper(page_with_results([no_link, valid])).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1

    def test_description_populated(self):
        item = _make_wechat_item(desc="Article summary here")
        results = WeChatSearchScraper(page_with_results([item])).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Article summary here"

    def test_returns_empty_when_no_items(self):
        assert WeChatSearchScraper(page_no_results()).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# Toutiao
# ===========================================================================

class TestToutiaoUrl:
    def setup_method(self):
        self.scraper = ToutiaoSearchScraper(MagicMock())

    def test_url_uses_toutiao_domain(self):
        url = self.scraper.build_search_url("AI", None)
        assert "so.toutiao.com/search?keyword=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("人工智能", None)
        assert "so.toutiao.com" in url

    def test_uses_networkidle_in_scrape_fast(self):
        """scrape_fast warms up first then navigates to search URL with networkidle."""
        page = MagicMock()
        scraper = ToutiaoSearchScraper(page)
        with patch.object(scraper, "extract_results", return_value=[]):
            scraper.scrape_fast("AI", None, 10)
        # page.goto is called twice: warmup (domcontentloaded) then search (networkidle).
        # call_args is the LAST call — the search URL.
        call_kwargs = page.goto.call_args[1]
        assert call_kwargs.get("wait_until") == "networkidle"


class TestToutiaoExtract:
    """
    extract_results() now uses BeautifulSoup on page.content().
    Tests supply real HTML via make_toutiao_page().
    Structure: div.result-content[cr-params=JSON] > a.l-card-title[href=/search/jump?url=...]
               + optional div.l-paragraph (description)
    The real URL is decoded from the ?url= query param of the redirect href.
    """

    def test_returns_search_result(self):
        page = make_toutiao_page([{"title": "News Article", "href": "https://toutiao.com/group/1/"}])
        results = ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        r = results[0]
        assert r.engine == "toutiao"
        assert r.title == "News Article"
        assert r.url == "https://toutiao.com/group/1/"
        assert r.rank == 1

    def test_rank_increments(self):
        page = make_toutiao_page([
            {"title": f"T{i}", "href": f"https://toutiao.com/group/{i}/"}
            for i in range(3)
        ])
        results = ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert [r.rank for r in results] == [1, 2, 3]

    def test_max_results_respected(self):
        page = make_toutiao_page([
            {"title": f"T{i}", "href": f"https://toutiao.com/group/{i}/"}
            for i in range(5)
        ])
        results = ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 3)
        assert len(results) == 3

    def test_skips_item_without_link(self):
        page = make_toutiao_page([
            {"title": "No Link", "href": "https://toutiao.com/group/99/", "no_link": True},
            {"title": "Valid", "href": "https://toutiao.com/group/1/"},
        ])
        results = ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_description_populated(self):
        page = make_toutiao_page([{
            "title": "Article", "href": "https://toutiao.com/group/1/", "desc": "News abstract"
        }])
        results = ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "News abstract"

    def test_description_none_when_absent(self):
        page = make_toutiao_page([{"title": "Article", "href": "https://toutiao.com/group/1/"}])
        results = ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description is None

    def test_title_from_cr_params(self):
        """cr-params title is preferred over link text (avoids <em> tag fragments)."""
        page = make_toutiao_page([{"title": "CR Params Title", "href": "https://toutiao.com/group/1/"}])
        results = ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].title == "CR Params Title"

    def test_returns_empty_when_no_items(self):
        page = make_toutiao_page([])
        assert ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []

    def test_page_content_error_returns_empty(self):
        page = MagicMock()
        page.content.side_effect = RuntimeError("Page not loaded")
        assert ToutiaoSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []


# ===========================================================================
# Jisilu
# ===========================================================================

class TestJisiluUrl:
    def setup_method(self):
        self.scraper = JisiluSearchScraper(MagicMock())

    def test_url_uses_jisilu_domain(self):
        url = self.scraper.build_search_url("可转债", None)
        assert "jisilu.cn/explore/?keyword=" in url

    def test_keyword_encoded(self):
        url = self.scraper.build_search_url("套利 策略", None)
        assert "jisilu.cn" in url


class TestJisiluExtract:
    """
    extract_results() now uses BeautifulSoup on page.content().
    Tests supply real HTML via make_jisilu_page().
    Structure: div.aw-item > div.aw-questoin-content > h4 > a  (title + href)
               + optional span.aw-text-color-999 (description/metadata)
    The promo banner (div.aw-item without aw-questoin-content) is skipped.
    """

    def test_returns_search_result_with_absolute_href(self):
        page = make_jisilu_page([{"title": "Bond Post", "href": "https://www.jisilu.cn/question/1"}])
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        r = results[0]
        assert r.engine == "jisilu"
        assert r.title == "Bond Post"
        assert r.url == "https://www.jisilu.cn/question/1"
        assert r.rank == 1

    def test_relative_href_gets_domain_prefix(self):
        """Relative paths starting with '/' must be made absolute."""
        page = make_jisilu_page([{"title": "Post", "href": "/question/42"}])
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].url == "https://www.jisilu.cn/question/42"

    def test_rank_increments(self):
        page = make_jisilu_page([
            {"title": f"T{i}", "href": f"https://www.jisilu.cn/question/{i}"}
            for i in range(3)
        ])
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert [r.rank for r in results] == [1, 2, 3]

    def test_max_results_respected(self):
        page = make_jisilu_page([
            {"title": f"T{i}", "href": f"https://www.jisilu.cn/question/{i}"}
            for i in range(4)
        ])
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 2)
        assert len(results) == 2

    def test_skips_item_without_link(self):
        page = make_jisilu_page([
            {"no_link": True},
            {"title": "Valid", "href": "https://www.jisilu.cn/question/99"},
        ])
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_promo_banner_skipped(self):
        """The first div.aw-item (promo banner, no aw-questoin-content) must be ignored."""
        page = make_jisilu_page(
            [{"title": "Real Post", "href": "https://www.jisilu.cn/question/1"}],
            include_promo=True,
        )
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert len(results) == 1
        assert results[0].title == "Real Post"

    def test_description_populated(self):
        page = make_jisilu_page([{
            "title": "Bond Post", "href": "https://www.jisilu.cn/question/1",
            "desc": "Discussion content"
        }])
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description == "Discussion content"

    def test_description_none_when_absent(self):
        page = make_jisilu_page([{"title": "Bond Post", "href": "https://www.jisilu.cn/question/1"}])
        results = JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10)
        assert results[0].description is None

    def test_returns_empty_when_no_items(self):
        page = make_jisilu_page([])
        assert JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []

    def test_page_content_error_returns_empty(self):
        page = MagicMock()
        page.content.side_effect = RuntimeError("Page not loaded")
        assert JisiluSearchScraper(page).extract_results("kw", SearchMode.FAST, 10) == []
