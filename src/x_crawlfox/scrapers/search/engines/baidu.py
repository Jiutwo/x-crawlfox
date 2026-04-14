from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode, TimeRange


class BaiduSearchScraper(BaseSearchScraper):
    engine_name = "baidu"
    home_url = "https://www.baidu.com"
    # Try new AI-style box first, fall back to classic input
    search_input_selectors = ["#chat-textarea", "#kw"]
    result_container_selector = ".c-container"

    _time_params = {
        TimeRange.HOUR:  "qdr:h",
        TimeRange.DAY:   "qdr:d",
        TimeRange.WEEK:  "qdr:w",
        TimeRange.MONTH: "qdr:m",
        TimeRange.YEAR:  "qdr:y",
    }

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        url = f"https://www.baidu.com/s?wd={quote_plus(q)}"
        if filters and filters.time_range:
            tbs = self._time_params.get(filters.time_range)
            if tbs:
                url += f"&tbs={tbs}"
        return url

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []

        try:
            containers = self.page.locator(".c-container").all()
        except Exception as e:
            logger.debug(f"[baidu] Failed to locate result containers: {e}")
            return results

        for container in containers:
            if len(results) >= max_results:
                break
            try:
                link_el = container.locator("h3 a").first
                if link_el.count() == 0:
                    continue

                title = link_el.inner_text().strip()
                href = link_el.get_attribute("href")
                if not title or not href:
                    continue

                description = None
                for sel in [".c-abstract", ".c-font-normal", ".c-span-last"]:
                    desc_el = container.locator(sel).first
                    if desc_el.count() > 0:
                        text = desc_el.inner_text().strip()
                        if text:
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
                logger.debug(f"[baidu] Failed to parse result item: {e}")

        logger.info(f"[baidu] Extracted {len(results)} results")
        return results
