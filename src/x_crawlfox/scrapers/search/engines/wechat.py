from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class WeChatSearchScraper(BaseSearchScraper):
    """WeChat article search via Sogou — wx.sogou.com"""

    engine_name = "wechat"
    home_url = ""
    search_input_selectors = []
    result_container_selector = ".news-box, .news_item"

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://wx.sogou.com/weixin?type=2&query={quote_plus(q)}"

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            items = self.page.locator(".news-box li, ul.news-list > li").all()
            if not items:
                items = self.page.locator(".news_item").all()
        except Exception as e:
            logger.debug(f"[wechat] Failed to locate result items: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                # Article title link
                link_el = item.locator("h3 a, a.txt").first
                if link_el.count() == 0:
                    link_el = item.locator("a[uigs]").first
                if link_el.count() == 0:
                    continue

                title = link_el.inner_text().strip()
                href = link_el.get_attribute("href")
                if not title or not href:
                    continue
                href = "https://wx.sogou.com" + href
                description = None
                for sel in [".txt-info", "p.txt", ".news-item-desc"]:
                    desc_el = item.locator(sel).first
                    if desc_el.count() > 0:
                        text = desc_el.inner_text().strip()
                        if text and text != title:
                            description = text
                            break

                results.append(SearchResult(
                    rank=len(results) + 1,
                    title=title,
                    url=href,
                    description=description,
                    engine=self.engine_name,
                    keyword=keyword,
                    mode=mode,
                ))
            except Exception as e:
                logger.debug(f"[wechat] Failed to parse result item: {e}")

        logger.info(f"[wechat] Extracted {len(results)} results")
        return results
