import random
from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode, TimeRange

# How long (ms) to wait for the user to manually solve a CAPTCHA in non-headless mode.
_CAPTCHA_WAIT_MS = 90_000


class GoogleSearchScraper(BaseSearchScraper):
    engine_name = "google"
    home_url = "https://www.google.com"

    # #APjFqb is the stable id of the textarea; fallbacks for other regions/variants
    search_input_selectors = ["#APjFqb", 'textarea[name="q"]', 'input[name="q"]']

    # #rso is the primary results block; #search is a wider fallback
    result_container_selector = "#rso"

    _time_params = {
        TimeRange.HOUR:  "qdr:h",
        TimeRange.DAY:   "qdr:d",
        TimeRange.WEEK:  "qdr:w",
        TimeRange.MONTH: "qdr:m",
        TimeRange.YEAR:  "qdr:y",
    }

    # ------------------------------------------------------------------
    # CAPTCHA detection helper
    # ------------------------------------------------------------------

    def _wait_if_captcha(self) -> bool:
        """
        Called right after any navigation that could trigger Google's CAPTCHA.

        Returns True if the page is (or becomes) a valid search results page.
        Returns False if the CAPTCHA could not be resolved and we should abort.
        """
        if "/sorry/" not in self.page.url:
            return True

        logger.warning(
            "[google] CAPTCHA page detected! "
            "If running with --no-headless, please solve the CAPTCHA in the "
            "browser window — waiting up to 90 seconds..."
        )
        try:
            # Wait for the URL to leave the /sorry/ path
            self.page.wait_for_url("**/search**", timeout=_CAPTCHA_WAIT_MS)
            logger.info("[google] CAPTCHA resolved, continuing...")
            self.page.wait_for_timeout(1000)
            return True
        except Exception:
            logger.error(
                "[google] CAPTCHA not resolved within timeout. "
                "Suggestions: (1) run with --no-headless and solve manually, "
                "(2) add a proxy via --proxy, "
                "(3) wait a while before retrying."
            )
            return False

    # ------------------------------------------------------------------
    # Scrape mode overrides — add CAPTCHA handling around navigation
    # ------------------------------------------------------------------

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(800, 1500))

        if not self._wait_if_captcha():
            return []

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

        # Allow navigation to settle before checking for CAPTCHA
        self.page.wait_for_timeout(2000)

        if not self._wait_if_captcha():
            return []

        self.page.wait_for_selector(self.result_container_selector, timeout=15000)
        self.page.wait_for_timeout(random.randint(1000, 2000))
        return self.extract_results(keyword, SearchMode.SIMULATE, max_results)

    # ------------------------------------------------------------------
    # Result extraction
    # ------------------------------------------------------------------

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        url = f"https://www.google.com/search?q={quote_plus(q)}"
        if filters:
            if filters.time_range:
                tbs = self._time_params.get(filters.time_range)
                if tbs:
                    url += f"&tbs={tbs}"
            if filters.language:
                url += f"&lr=lang_{filters.language}"
        return url

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []

        # Iterate h3 elements inside the results area and walk up via XPath
        # ancestors to get the link and description.  This avoids relying on
        # class names like ".g" that Google changes frequently.
        try:
            h3_elements = self.page.locator("#rso h3, #search h3").all()
        except Exception as e:
            logger.debug(f"[google] Failed to locate h3 elements: {e}")
            return results

        for h3 in h3_elements:
            if len(results) >= max_results:
                break
            try:
                title = h3.inner_text().strip()
                if not title:
                    continue

                # Nearest <a> ancestor carries the real destination URL
                link_el = h3.locator("xpath=ancestor::a[@href][1]").first
                if link_el.count() == 0:
                    link_el = h3.locator("xpath=..//a[@href]").first
                if link_el.count() == 0:
                    continue

                href = link_el.get_attribute("href")
                if not href or href.startswith("#") or "/search?" in href:
                    continue

                # Description: walk up ~4 div levels to the result card
                description = None
                card = h3.locator("xpath=ancestor::div[4]").first
                if card.count() > 0:
                    for sel in [".VwiC3b", "[data-sncf='1']", ".IsZvec", "span[style]"]:
                        desc_el = card.locator(sel).first
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
                logger.debug(f"[google] Failed to parse result item: {e}")

        logger.info(f"[google] Extracted {len(results)} results")
        return results
