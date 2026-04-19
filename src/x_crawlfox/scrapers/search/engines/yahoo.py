import random
from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class YahooSearchScraper(BaseSearchScraper):
    """Yahoo Search — search.yahoo.com

    Actual result HTML structure (class names are stable):
      <div class="... algo ...">
        <div class="compTitle">
          <a href="https://actual-url">      ← href lives here
            <h3 class="title ...">           ← title text lives here (a's child)
              <span>Title text</span>
            </h3>
          </a>
        </div>
        <div class="compText">
          <p class="fc-dustygray ...">description text</p>
        </div>
      </div>

    Note: the <a> is the *parent* of <h3>, not the other way around.
    """

    engine_name = "yahoo"
    home_url = ""
    search_input_selectors = []
    result_container_selector = "div.algo"

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://search.yahoo.com/search?p={quote_plus(q)}"

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        except Exception as e:
            if "NS_ERROR_ABORT" not in str(e) and "ERR_ABORTED" not in str(e):
                raise
            # Yahoo's redirect chain occasionally aborts the initial navigation.
            # Wait briefly and retry once with a looser wait strategy.
            logger.debug(f"[yahoo] Navigation aborted, retrying: {e}")
            self.page.wait_for_timeout(2000)
            try:
                self.page.goto(url, wait_until="networkidle", timeout=self.goto_timeout)
            except Exception as retry_e:
                if "NS_ERROR_ABORT" not in str(retry_e) and "ERR_ABORTED" not in str(retry_e):
                    raise
                logger.debug(f"[yahoo] Retry also aborted, proceeding with extraction: {retry_e}")
        self.page.wait_for_timeout(random.randint(800, 1500))
        return self.extract_results(keyword, SearchMode.FAST, max_results)

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            items = self.page.locator("div.algo").all()
        except Exception as e:
            logger.debug(f"[yahoo] Failed to locate result items: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                # href is on the <a> in div.compTitle (the <a> wraps the <h3>)
                link_el = item.locator("div.compTitle a").first
                if link_el.count() == 0:
                    continue
                href = link_el.get_attribute("href") or ""
                if not href or href.startswith("#"):
                    continue

                # title text lives inside the <h3> that is a child of the <a>
                title_el = item.locator("h3.title").first
                title = title_el.inner_text().strip() if title_el.count() > 0 else ""
                if not title:
                    continue

                description = None
                desc_el = item.locator("div.compText p").first
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
                logger.debug(f"[yahoo] Failed to parse result item: {e}")

        logger.info(f"[yahoo] Extracted {len(results)} results")
        return results
