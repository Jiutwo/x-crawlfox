import random
from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger
from bs4 import BeautifulSoup

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class StartpageSearchScraper(BaseSearchScraper):
    """Startpage — privacy-preserving Google proxy.

    Startpage uses CSS-in-JS (Emotion) so class names like ``w-gl__result``
    are paired with unstable hashes (``css-14ta8x9``).  The stable anchor is
    the semantic class ``result`` on each ``<div class="result …">`` container.

    Anti-detection notes:
      - ``wait_for_selector`` with state="visible" reliably times out here
        because React re-renders during hydration change the element repeatedly.
        We wait for ``networkidle`` (or a generous fixed delay) instead.
      - Extraction uses BeautifulSoup on the full page HTML so we are not
        racing against React's DOM mutations.
    """

    engine_name = "startpage"
    home_url = "https://www.startpage.com/"
    search_input_selectors = [
        'input[name="q"]',
        'input[type="search"]',
        '#q',
    ]
    # Only used as a fallback reference; scrape_fast overrides the wait logic.
    result_container_selector = ".result"
    goto_timeout = 90_000

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://www.startpage.com/sp/search?query={quote_plus(q)}"

    # ------------------------------------------------------------------
    # Scrape modes  (both override base to avoid wait_for_selector race)
    # ------------------------------------------------------------------

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        # domcontentloaded fires early; networkidle lets React finish hydrating.
        self.page.goto(url, wait_until="networkidle", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(800, 1500))
        return self.extract_results(keyword, SearchMode.FAST, max_results)

    def scrape_simulate(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        effective_keyword = self.build_keyword_with_operators(keyword, filters)
        logger.info(f"[{self.engine_name}] Simulate → typing '{effective_keyword}'")

        self.page.goto(self.home_url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(1000, 2000))

        search_input = self._find_search_input()
        if search_input is None:
            logger.warning(f"[{self.engine_name}] Search input not found, falling back to fast mode")
            return self.scrape_fast(keyword, filters, max_results)

        search_input.click()
        self.page.wait_for_timeout(random.randint(200, 500))
        self.page.keyboard.type(effective_keyword, delay=random.randint(70, 140))
        self.page.wait_for_timeout(random.randint(300, 700))
        self.page.keyboard.press("Enter")

        self.page.wait_for_load_state("networkidle", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(800, 1500))
        return self.extract_results(keyword, SearchMode.SIMULATE, max_results)

    # ------------------------------------------------------------------
    # Result extraction  (BeautifulSoup — immune to DOM mutation races)
    # ------------------------------------------------------------------

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            html = self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            # Match both <div class="result …"> and <article class="result …">
            items = soup.select("div.result, article.result")
            logger.debug(f"[startpage] Found {len(items)} result items")
        except Exception as e:
            logger.debug(f"[startpage] Failed to get/parse page: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                # Title + URL: first <a> inside an <h2> or <h3>
                title_el = None
                for heading_tag in ("h2", "h3"):
                    heading = item.find(heading_tag)
                    if heading:
                        title_el = heading.find("a")
                        if title_el:
                            break
                # Fallback: any <a> with class "result-title"
                if not title_el:
                    title_el = item.find("a", class_="result-title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                href = title_el.get("href", "").strip()
                if not title or not href:
                    continue

                # Description: first <p> that is not the title text
                description = None
                for p in item.find_all("p"):
                    text = p.get_text(strip=True)
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
                logger.debug(f"[startpage] Failed to parse result item: {e}")

        logger.info(f"[startpage] Extracted {len(results)} results")
        return results
