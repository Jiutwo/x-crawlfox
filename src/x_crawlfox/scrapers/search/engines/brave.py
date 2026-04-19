from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class BraveSearchScraper(BaseSearchScraper):
    """Brave Search — independent index, no tracking."""

    engine_name = "brave"
    home_url = ""
    search_input_selectors = []
    result_container_selector = "#results, .snippet"

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://search.brave.com/search?q={quote_plus(q)}"

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            items = self.page.locator("div.snippet[data-type='web'], div.snippet").all()
        except Exception as e:
            logger.debug(f"[brave] Failed to locate result items: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                link_el = item.locator("a.heading-serpresult, a[href][data-type]").first
                if link_el.count() == 0:
                    link_el = item.locator("a.result-header").first
                if link_el.count() == 0:
                    link_el = item.locator("a[href]").first
                if link_el.count() == 0:
                    continue

                title_el = item.locator(".snippet-title, span.title, h3, h2").first
                title = title_el.inner_text().strip() if title_el.count() > 0 else link_el.inner_text().strip()
                href = link_el.get_attribute("href")
                if not title or not href or href.startswith("#"):
                    continue

                description = None
                for sel in [".snippet-description, .snippet-content, p"]:
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
                logger.debug(f"[brave] Failed to parse result item: {e}")

        logger.info(f"[brave] Extracted {len(results)} results")
        return results
