import random
from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger
from bs4 import BeautifulSoup

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class QwantSearchScraper(BaseSearchScraper):
    """Qwant — EU-based, GDPR-compliant search engine.

    Qwant renders via React with CSS-in-JS class names (unstable on each deploy).
    Only ``data-testid`` attributes and structural relationships are used.

    Each result is a ``div[data-testid="webResult"]`` with a ``domain`` attribute
    that holds the result URL directly.  Inside, there are several ``<a class="external">``
    links; the title link is identified by exclusion:
      - Links with ``<img>`` inside  → favicon links (skip)
      - Links inside ``[data-testid="domain"]``  → domain / breadcrumb links (skip)
      - Links with multiple CSS classes  → breadcrumb links (skip)
      → The remaining single-class ``<a class="external">`` is the title link.

    The description is the sibling ``<div>`` immediately after the title ``<a>``
    within the same parent element.

    Anti-detection notes:
      - Homepage is visited first on every scrape to establish a legitimate session
        and receive GDPR cookies before any search request is made.
      - The GDPR/cookie consent banner is dismissed automatically if present.
      - ``wait_until="domcontentloaded"`` is used instead of ``networkidle``
        (the latter is a bot signal; real users don't wait for networkidle).
    """

    engine_name = "qwant"
    home_url = "https://www.qwant.com/"
    search_input_selectors = [
        'input[name="q"]',
        'input[type="search"]',
        '#qwant-search',
        '[data-testid="search-input"]',
    ]
    result_container_selector = '[data-testid="webResult"]'
    goto_timeout = 90_000

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _warmup_homepage(self):
        """Visit homepage and dismiss any consent banner.

        Qwant (and Cloudflare in front of it) issue session cookies on the
        first homepage visit.  Jumping straight to the search URL without
        these cookies triggers the bot-detection redirect.
        """
        logger.info(f"[{self.engine_name}] Warming up via homepage…")
        self.page.goto(self.home_url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(1500, 3000))
        self._dismiss_consent()
        self.page.wait_for_timeout(random.randint(500, 1200))

    def _dismiss_consent(self):
        """Dismiss GDPR / cookie consent banner if present."""
        consent_selectors = [
            '[data-testid="cookie-accept"]',
            '#didomi-notice-agree-button',
            'button[id*="accept"]',
            'button:has-text("Accept")',
            'button:has-text("Accepter")',
            'button:has-text("J\'accepte")',
        ]
        for sel in consent_selectors:
            try:
                btn = self.page.locator(sel).first
                if btn.count() > 0:
                    btn.wait_for(state="visible", timeout=3000)
                    btn.click()
                    self.page.wait_for_timeout(random.randint(400, 900))
                    logger.debug(f"[qwant] Consent dismissed via: {sel}")
                    return
            except Exception:
                continue

    def _wait_for_results(self):
        try:
            self.page.wait_for_selector('[data-testid="webResult"]', timeout=30_000)
            logger.debug("[qwant] First webResult detected")
        except Exception as e:
            logger.debug(f"[qwant] Timed out waiting for webResult: {e}")

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://www.qwant.com/?q={quote_plus(q)}&t=web"

    # ------------------------------------------------------------------
    # Scrape modes
    # ------------------------------------------------------------------

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        # Warm up first so Qwant sees a legitimate session before the search URL
        self._warmup_homepage()

        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        self._wait_for_results()
        self.page.wait_for_timeout(random.randint(1000, 2000))
        return self.extract_results(keyword, SearchMode.FAST, max_results)

    def scrape_simulate(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        effective_keyword = self.build_keyword_with_operators(keyword, filters)
        logger.info(f"[{self.engine_name}] Simulate → typing '{effective_keyword}'")

        self._warmup_homepage()

        search_input = self._find_search_input()
        if search_input is None:
            logger.warning(f"[{self.engine_name}] Search input not found, falling back to fast mode")
            return self.scrape_fast(keyword, filters, max_results)

        search_input.click()
        self.page.wait_for_timeout(random.randint(200, 500))
        self.page.keyboard.type(effective_keyword, delay=random.randint(80, 160))
        self.page.wait_for_timeout(random.randint(400, 900))
        self.page.keyboard.press("Enter")

        self._wait_for_results()
        self.page.wait_for_timeout(random.randint(1000, 2000))
        return self.extract_results(keyword, SearchMode.SIMULATE, max_results)

    # ------------------------------------------------------------------
    # Result extraction
    # ------------------------------------------------------------------

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            html = self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select('[data-testid="webResult"]')
            logger.debug(f"[qwant] Found {len(items)} webResult items")
        except Exception as e:
            logger.debug(f"[qwant] Failed to get/parse page: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                # URL lives in the 'domain' attribute of the container div
                href = (item.get("domain") or "").strip()
                if not href or not href.startswith("http"):
                    continue

                # Title link: <a class="external"> (single class) that
                #   - is not inside [data-testid="domain"] (domain/favicon links)
                #   - does not wrap an <img> (favicon link)
                #   - has readable non-URL text
                title = ""
                title_el = None
                for a in item.find_all("a", class_="external"):
                    if len(a.get("class", [])) != 1:           # breadcrumbs have extra classes
                        continue
                    if a.find("img"):                           # favicon link
                        continue
                    if a.find_parent(attrs={"data-testid": "domain"}):
                        continue
                    text = a.get_text(strip=True)
                    if text and not text.startswith(("http://", "https://")):
                        title = text
                        title_el = a
                        break

                if not title:
                    continue

                # Description: first sibling Tag after the title <a> in its parent
                description = None
                if title_el is not None:
                    parent = title_el.parent
                    found = False
                    for child in parent.children:
                        if child is title_el:
                            found = True
                            continue
                        if found and getattr(child, "name", None):
                            text = child.get_text(strip=True)
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
                logger.debug(f"[qwant] Failed to parse result item: {e}")

        logger.info(f"[qwant] Extracted {len(results)} results")
        return results
