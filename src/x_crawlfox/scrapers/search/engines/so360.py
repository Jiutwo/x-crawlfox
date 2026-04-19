from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class So360SearchScraper(BaseSearchScraper):
    """360 Search — so.com"""

    engine_name = "360"
    home_url = ""
    search_input_selectors = []
    result_container_selector = "li.res-list"

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://www.so.com/s?q={quote_plus(q)}"

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            items = self.page.locator("li.res-list").all()
        except Exception as e:
            logger.debug(f"[360] Failed to locate result items: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                link_el = item.locator("h3 a").first
                if link_el.count() == 0:
                    continue
                title = link_el.inner_text().strip()
                href = link_el.get_attribute("href")
                if not title or not href:
                    continue

                description = None
                for sel in [".res-desc", ".res-comm-con", "p"]:
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
                logger.debug(f"[360] Failed to parse result item: {e}")

        logger.info(f"[360] Extracted {len(results)} results")
        return results
