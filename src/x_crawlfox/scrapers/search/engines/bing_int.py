from typing import Optional
from urllib.parse import quote_plus

from .bing import BingSearchScraper
from ....models.search_schema import SearchFilter


class BingINTSearchScraper(BingSearchScraper):
    """Bing INT — cn.bing.com with international results (ensearch=1)."""

    engine_name = "bing-int"
    home_url = ""
    search_input_selectors = []

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        url = f"https://cn.bing.com/search?q={quote_plus(q)}&ensearch=1"
        if filters and filters.time_range:
            filter_val = self._time_params.get(filters.time_range)
            if filter_val:
                url += f"&filters={quote_plus(filter_val)}"
        return url
