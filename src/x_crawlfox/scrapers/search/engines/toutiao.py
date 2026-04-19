import json
import random
from typing import List, Optional
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from loguru import logger
from bs4 import BeautifulSoup

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode


class ToutiaoSearchScraper(BaseSearchScraper):
    """Toutiao Search — so.toutiao.com

    Result structure::

        div.result-content[cr-params=JSON]    ← each card
            a.l-card-title.h3[href=/search/jump?...&url=REAL_URL&...]  ← title link
            div.l-paragraph.t2                ← description

    Key quirks:
      - Title link href is a redirect ``/search/jump?...&url={encoded}&...``
        The real URL is URL-decoded from the ``url`` query parameter.
        Fallback: ``https://toutiao.com/group/{gid}/`` from ``cr-params``.
      - ``cr-params`` attribute (HTML-entity-encoded JSON) contains ``title``
        and ``gid`` — useful when the link text has partial ``<em>`` wrapping.
      - ``wait_until="networkidle"`` is intentional: Toutiao is React SSR +
        client hydration and results only appear after JS execution.
    """

    engine_name = "toutiao"
    home_url = "https://so.toutiao.com/"
    search_input_selectors = [
        'input[name="keyword"]',
        'input[type="search"]',
        '.search-bar input',
        '#search-input',
    ]
    result_container_selector = "div.result-content"
    goto_timeout = 90_000

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://so.toutiao.com/search?keyword={quote_plus(q)}&dvpf=pc"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_redirect_url(href: str, gid: str = "") -> str:
        """Extract the real destination URL from Toutiao's /search/jump redirect."""
        try:
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            if "url" in params:
                real = unquote(params["url"][0])
                if real.startswith("http"):
                    return real
        except Exception:
            pass
        # Fallback: construct from group id
        if gid:
            return f"https://toutiao.com/group/{gid}/"
        return href

    def _warmup_homepage(self):
        """Visit so.toutiao.com first to establish a same-domain session.

        Warming up on www.toutiao.com is useless because cookies are not shared
        across subdomains; the search endpoint is so.toutiao.com.
        """
        logger.info(f"[{self.engine_name}] Warming up via so.toutiao.com…")
        self.page.goto("https://so.toutiao.com/", wait_until="domcontentloaded", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(2500, 4000))
        # Light scroll to look more human
        self.page.mouse.wheel(0, random.randint(100, 300))
        self.page.wait_for_timeout(random.randint(500, 1000))

    def _diagnose_page(self):
        """Log current URL + page title to help identify what block page we landed on."""
        try:
            current_url = self.page.url
            title = self.page.title()
            logger.warning(f"[{self.engine_name}] Blocked? current URL: {current_url}")
            logger.warning(f"[{self.engine_name}] Page title: {title}")
            # Dump a short text snippet for further clues
            body_text = self.page.locator("body").inner_text()[:400].replace("\n", " ")
            logger.warning(f"[{self.engine_name}] Body snippet: {body_text}")
        except Exception as e:
            logger.debug(f"[{self.engine_name}] _diagnose_page error: {e}")

    # ------------------------------------------------------------------
    # Scrape modes
    # ------------------------------------------------------------------

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        self._warmup_homepage()
        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        self.page.goto(url, wait_until="networkidle", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(2000, 3000))
        results = self.extract_results(keyword, SearchMode.FAST, max_results)
        if not results:
            self._diagnose_page()
        return results

    def scrape_simulate(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        effective_keyword = self.build_keyword_with_operators(keyword, filters)
        logger.info(f"[{self.engine_name}] Simulate → typing '{effective_keyword}'")

        self.page.goto(self.home_url, wait_until="domcontentloaded", timeout=self.goto_timeout)
        self.page.wait_for_timeout(random.randint(2500, 4000))
        self.page.mouse.wheel(0, random.randint(100, 300))
        self.page.wait_for_timeout(random.randint(500, 1000))

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
        self.page.wait_for_timeout(random.randint(1500, 2500))
        results = self.extract_results(keyword, SearchMode.SIMULATE, max_results)
        if not results:
            self._diagnose_page()
        return results

    # ------------------------------------------------------------------
    # Result extraction
    # ------------------------------------------------------------------

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            html = self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select("div.result-content")
            logger.debug(f"[toutiao] Found {len(items)} result-content items")
        except Exception as e:
            logger.debug(f"[toutiao] Failed to get/parse page: {e}")
            return results

        for item in items:
            if len(results) >= max_results:
                break
            try:
                # ── cr-params: reliable source for title + gid ──────────
                gid = ""
                cr_title = ""
                cr_raw = item.get("cr-params", "")
                if cr_raw:
                    try:
                        cr = json.loads(cr_raw)
                        gid = cr.get("gid", "")
                        cr_title = cr.get("title", "")
                    except Exception:
                        pass

                # ── Title link: <a class="... l-card-title ..."> ─────────
                # The <a> itself carries l-card-title; its parent div may too.
                title_el = item.select_one("a.l-card-title")
                if not title_el:
                    # Fallback: any <a> whose href is a /search/jump redirect
                    title_el = item.find("a", href=lambda h: h and "/search/jump" in h)
                if not title_el:
                    continue

                # Prefer cr-params title (no stray <em> fragments)
                title = cr_title or title_el.get_text(strip=True)
                if not title:
                    continue

                # ── URL: decode from redirect href ────────────────────────
                raw_href = title_el.get("href", "")
                if raw_href.startswith("/"):
                    raw_href = f"https://so.toutiao.com{raw_href}"
                href = self._decode_redirect_url(raw_href, gid)
                if not href:
                    continue

                # ── Description: div.l-paragraph ─────────────────────────
                description = None
                para = item.select_one("div.l-paragraph")
                if para:
                    text = para.get_text(strip=True)
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
                logger.debug(f"[toutiao] Failed to parse result item: {e}")

        logger.info(f"[toutiao] Extracted {len(results)} results")
        return results
