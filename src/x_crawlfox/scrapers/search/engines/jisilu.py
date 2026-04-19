import random
from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger
from bs4 import BeautifulSoup

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class JisiluSearchScraper(BaseSearchScraper):
    """Jisilu (集思录) — Chinese bond/fund investment forum search.

    The explore page lists each post as::

        div.aw-item
            span.aw-question-replay-count   ← reply count
            div.aw-questoin-content         ← NOTE: intentional typo in Jisilu's HTML
                h4 > a[href]                ← title + URL
                span.aw-text-color-999      ← category • author • time • views

    The first ``div.aw-item`` on the page is a promo/ad banner (no
    ``aw-questoin-content`` child) and is skipped automatically.
    """

    engine_name = "jisilu"
    home_url = "https://www.jisilu.cn/"
    search_input_selectors = [
        'input[name="q"]',
        'input[type="search"]',
        '#aw-search-input',
        '.aw-search-input',
    ]
    result_container_selector = "div.aw-item"
    goto_timeout = 60_000

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://www.jisilu.cn/explore/?keyword={quote_plus(q)}"

    # ------------------------------------------------------------------
    # Scrape modes
    # ------------------------------------------------------------------

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        self.page.goto(url, wait_until="networkidle", timeout=self.goto_timeout)
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
        self.page.wait_for_timeout(random.randint(200, 500))
        self.page.keyboard.type(effective_keyword, delay=random.randint(80, 160))
        self.page.wait_for_timeout(random.randint(300, 700))
        self.page.keyboard.press("Enter")

        self.page.wait_for_load_state("networkidle", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(800, 1500))
        return self.extract_results(keyword, SearchMode.SIMULATE, max_results)

    # ------------------------------------------------------------------
    # Result extraction
    # ------------------------------------------------------------------

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            html = self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            # Filter: only div.aw-item that contain div.aw-questoin-content
            # (the promo banner at the top is also div.aw-item but lacks this child)
            items = [
                el for el in soup.select("div.aw-item")
                if el.find("div", class_="aw-questoin-content")
            ]
            logger.debug(f"[jisilu] Found {len(items)} result items")
        except Exception as e:
            logger.debug(f"[jisilu] Failed to get/parse page: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                content = item.find("div", class_="aw-questoin-content")
                if not content:
                    continue

                # Title + URL: h4 > a
                h4 = content.find("h4")
                if not h4:
                    continue
                a = h4.find("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                href = (a.get("href") or "").strip()
                if not title or not href:
                    continue
                if href.startswith("/"):
                    href = f"https://www.jisilu.cn{href}"

                # Description: metadata line — category • author • time • view count
                description = None
                meta = content.find("span", class_="aw-text-color-999")
                if meta:
                    description = meta.get_text(separator=" ", strip=True)

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
                logger.debug(f"[jisilu] Failed to parse result item: {e}")

        logger.info(f"[jisilu] Extracted {len(results)} results")
        return results
