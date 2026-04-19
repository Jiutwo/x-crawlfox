from typing import Optional
from urllib.parse import quote_plus

from .bing import BingSearchScraper
from ....models.search_schema import SearchFilter


class BingCNSearchScraper(BingSearchScraper):
    """Bing CN — cn.bing.com with Chinese results (ensearch=0)."""

    engine_name = "bing-cn"
    home_url = ""
    search_input_selectors = []

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        url = f"https://cn.bing.com/search?q={quote_plus(q)}&ensearch=0"
        if filters and filters.time_range:
            filter_val = self._time_params.get(filters.time_range)
            if filter_val:
                url += f"&filters={quote_plus(filter_val)}"
        return url
