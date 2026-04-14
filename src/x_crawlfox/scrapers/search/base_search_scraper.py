import random
from abc import ABC, abstractmethod
from typing import List, Optional
from urllib.parse import quote_plus
from playwright.sync_api import Page
from loguru import logger

from ...models.search_schema import SearchResult, SearchFilter, SearchMode


class BaseSearchScraper(ABC):
    engine_name: str = ""
    home_url: str = ""
    # Tried in order — first visible one wins
    search_input_selectors: List[str] = []
    result_container_selector: str = ""
    # Timeout (ms) for page.goto — increase for slow networks / regional restrictions
    goto_timeout: int = 60000

    def __init__(self, page: Page):
        self.page = page

    # ------------------------------------------------------------------
    # Keyword operator injection (shared by both modes)
    # ------------------------------------------------------------------

    def build_keyword_with_operators(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        """Append site:, filetype:, exact phrase, and exclusion operators to keyword."""
        if not filters:
            return keyword

        parts = []
        if filters.exact_phrase:
            parts.append(f'"{filters.exact_phrase}"')
        else:
            parts.append(keyword)

        if filters.site:
            parts.append(f"site:{filters.site}")
        if filters.filetype:
            parts.append(f"filetype:{filters.filetype}")
        if filters.exclude_terms:
            for term in filters.exclude_terms:
                parts.append(f"-{term}")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Abstract interface — each engine must implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        """Return the full search URL with all relevant URL params applied."""

    @abstractmethod
    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        """Extract results from the already-loaded page (reads self.page)."""

    # ------------------------------------------------------------------
    # Scrape modes
    # ------------------------------------------------------------------

    def _find_search_input(self):
        """Try each selector in order; return the first visible element."""
        for selector in self.search_input_selectors:
            elem = self.page.locator(selector).first
            if elem.count() > 0:
                try:
                    elem.wait_for(state="visible", timeout=3000)
                    return elem
                except Exception:
                    continue
        return None

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        self.page.wait_for_selector(self.result_container_selector, timeout=15000)
        self.page.wait_for_timeout(random.randint(800, 1500))
        return self.extract_results(keyword, SearchMode.FAST, max_results)

    def scrape_simulate(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        effective_keyword = self.build_keyword_with_operators(keyword, filters)
        logger.info(f"[{self.engine_name}] Simulate → typing '{effective_keyword}'")

        self.page.goto(self.home_url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(800, 1800))

        search_input = self._find_search_input()
        if search_input is None:
            logger.warning(f"[{self.engine_name}] Search input not found, falling back to fast mode")
            return self.scrape_fast(keyword, filters, max_results)

        search_input.click()
        self.page.keyboard.type(effective_keyword, delay=random.randint(60, 150))
        self.page.wait_for_timeout(random.randint(300, 700))
        self.page.keyboard.press("Enter")

        self.page.wait_for_selector(self.result_container_selector, timeout=15000)
        self.page.wait_for_timeout(random.randint(1000, 2000))

        return self.extract_results(keyword, SearchMode.SIMULATE, max_results)

    def scrape(
        self,
        keyword: str,
        mode: SearchMode = SearchMode.SIMULATE,
        filters: Optional[SearchFilter] = None,
        max_results: int = 10,
    ) -> List[SearchResult]:
        try:
            if mode == SearchMode.FAST:
                return self.scrape_fast(keyword, filters, max_results)
            return self.scrape_simulate(keyword, filters, max_results)
        except Exception as e:
            logger.error(f"[{self.engine_name}] Scrape failed: {e}")
            return []
