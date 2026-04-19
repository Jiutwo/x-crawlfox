from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode, TimeRange


class BingSearchScraper(BaseSearchScraper):
    engine_name = "bing"
    home_url = "https://www.bing.com"
    search_input_selectors = ["#sb_form_q"]
    result_container_selector = "#b_results"

    # Bing uses filter strings in the `filters` URL param
    _time_params = {
        TimeRange.DAY:   'ex1:"ez5"',
        TimeRange.WEEK:  'ex1:"ez3"',
        TimeRange.MONTH: 'ex1:"ez2"',
    }

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        url = f"https://www.bing.com/search?q={quote_plus(q)}"
        if filters and filters.time_range:
            filter_val = self._time_params.get(filters.time_range)
            if filter_val:
                url += f"&filters={quote_plus(filter_val)}"
        return url

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []

        try:
            blocks = self.page.locator("li.b_algo").all()
        except Exception as e:
            logger.debug(f"[bing] Failed to locate result blocks: {e}")
            return results

        for block in blocks:
            if len(results) >= max_results:
                break
            try:
                link_el = block.locator("h2 a").first
                if link_el.count() == 0:
                    continue

                title = link_el.inner_text().strip()
                href = link_el.get_attribute("href")
                if not title or not href:
                    continue

                description = None
                desc_el = block.locator("p").first
                if desc_el.count() > 0:
                    text = desc_el.inner_text().strip()
                    if text:
                        description = text

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
                logger.debug(f"[bing] Failed to parse result item: {e}")

        logger.info(f"[bing] Extracted {len(results)} results")
        return results
