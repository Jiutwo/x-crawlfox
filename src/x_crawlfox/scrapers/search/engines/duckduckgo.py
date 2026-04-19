from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class DuckDuckGoSearchScraper(BaseSearchScraper):
    """DuckDuckGo — HTML endpoint, no JS required."""

    engine_name = "duckduckgo"
    home_url = ""
    search_input_selectors = []
    result_container_selector = ".results, #links"

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://duckduckgo.com/html/?q={quote_plus(q)}"

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            items = self.page.locator(".results_links, .result").all()
        except Exception as e:
            logger.debug(f"[duckduckgo] Failed to locate result items: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                link_el = item.locator("a.result__a, h2 a").first
                if link_el.count() == 0:
                    continue
                title = link_el.inner_text().strip()
                href = link_el.get_attribute("href")
                if not title or not href:
                    continue
                # DDG HTML wraps URLs in a redirect — use as-is
                if href.startswith("//"):
                    href = "https:" + href

                description = None
                desc_el = item.locator(".result__snippet, .snippet").first
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
                logger.debug(f"[duckduckgo] Failed to parse result item: {e}")

        logger.info(f"[duckduckgo] Extracted {len(results)} results")
        return results
