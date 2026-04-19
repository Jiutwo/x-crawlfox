from typing import List, Optional
from urllib.parse import quote_plus
from loguru import logger
from bs4 import BeautifulSoup

from ..base_search_scraper import BaseSearchScraper
from ....models.search_schema import SearchResult, SearchFilter, SearchMode

# Maximum character length for the merged description field.
_MAX_DESC = 3000


class WolframAlphaSearchScraper(BaseSearchScraper):
    """WolframAlpha — computational knowledge engine.

    All answer pods are merged into a **single** SearchResult so the output
    reads as one coherent answer rather than a list of disconnected fragments.

    Description format (pods separated by blank lines):
        Pod Title 1
        pod content text…

        Pod Title 2
        pod content text…

    WolframAlpha renders result text as images; all readable content lives in
    the ``alt`` attribute of those images.  Class names are CSS-in-JS generated
    (change on every deploy), so only stable structural attributes are used:
      - Pod container : ``section[tabindex='0']``
      - Title         : ``div[target='header'] h2 span``  → inner text
      - Content       : ``img[alt]``                       → alt attribute
    """

    engine_name = "wolframalpha"
    home_url = ""
    search_input_selectors = []
    result_container_selector = ""   # unused; BS4 handles extraction
    goto_timeout = 90_000

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        return f"https://www.wolframalpha.com/input?i={quote_plus(q)}"

    def scrape_fast(self, keyword: str, filters: Optional[SearchFilter], max_results: int) -> List[SearchResult]:
        import random
        url = self.build_search_url(keyword, filters)
        logger.info(f"[{self.engine_name}] Fast → {url}")
        self.page.goto(url, wait_until="networkidle", timeout=self.goto_timeout)
        # Pods render asynchronously after networkidle; wait until the first one appears.
        try:
            self.page.wait_for_selector("section[tabindex='0']", timeout=45_000)
            logger.debug("[wolframalpha] First pod detected; waiting for remaining pods")
        except Exception as e:
            logger.debug(f"[wolframalpha] Timed out waiting for pods: {e}")
        # Give the remaining pods time to finish rendering progressively.
        self.page.wait_for_timeout(random.randint(3000, 5000))
        return self.extract_results(keyword, SearchMode.FAST, max_results)

    def extract_results(self, keyword: str, mode: SearchMode, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        query_url = self.build_search_url(keyword, None)
        try:
            html = self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            pods = soup.select("section[tabindex='0']")
            logger.debug(f"[wolframalpha] Found {len(pods)} pods in HTML ({len(html)} bytes)")
        except Exception as e:
            logger.debug(f"[wolframalpha] Failed to get/parse page: {e}")
            return results

        # Collect each pod as "Title\ncontent" then merge into one result.
        parts: List[str] = []
        for pod in pods:
            try:
                title_el = pod.select_one("div[target='header'] h2 span")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                img_el = pod.select_one("img[alt]")
                alt_text = (img_el.get("alt") or "").strip() if img_el else ""

                if alt_text and alt_text != title:
                    parts.append(f"{title}\n{alt_text}")
                else:
                    parts.append(title)
            except Exception as e:
                logger.debug(f"[wolframalpha] Failed to parse pod: {e}")

        if parts:
            description = "\n\n".join(parts)
            if len(description) > _MAX_DESC:
                description = description[:_MAX_DESC]
            results.append(SearchResult(
                rank=1,
                title=keyword,
                url=query_url,
                description=description,
                engine=self.engine_name,
                keyword=keyword,
                mode=mode,
            ))

        logger.info(f"[wolframalpha] Merged {len(parts)} pods → {len(results)} result")
        return results
