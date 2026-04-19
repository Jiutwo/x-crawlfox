from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class EcosiaSearchScraper(BaseSearchScraper):
    """Ecosia — eco-friendly search engine.

    Actual result HTML structure (data-test-id attributes are stable):
      <article data-test-id="organic-result" class="result web-result ...">
        <div class="result__title">
          <a class="result__link" href="https://actual-url">
            <h2 data-test-id="result-title" class="result-title__heading">Title</h2>
          </a>
        </div>
        <p data-test-id="web-result-description" class="web-result__description">
          description text
        </p>
      </article>

    Note: the <a class="result__link"> wraps <h2>, so title = link.inner_text().
    CSS class names are CSS-in-JS generated; data-test-id attributes are stable.
    """

    engine_name = "ecosia"
    home_url = ""
    search_input_selectors = []
    result_container_selector = 'article[data-test-id="organic-result"]'

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://www.ecosia.org/search?q={quote_plus(q)}"

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            items = self.page.locator('article[data-test-id="organic-result"]').all()
        except Exception as e:
            logger.debug(f"[ecosia] Failed to locate result items: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                # <a class="result__link"> wraps <h2> — href and title both from this element
                link_el = item.locator("a.result__link").first
                if link_el.count() == 0:
                    continue
                href = link_el.get_attribute("href") or ""
                if not href or href.startswith("#"):
                    continue
                title = link_el.inner_text().strip()
                if not title:
                    continue

                description = None
                desc_el = item.locator('p[data-test-id="web-result-description"]').first
                if desc_el.count() > 0:
                    text = desc_el.inner_text().strip()
                    if text and text != title:
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
                logger.debug(f"[ecosia] Failed to parse result item: {e}")

        logger.info(f"[ecosia] Extracted {len(results)} results")
        return results
