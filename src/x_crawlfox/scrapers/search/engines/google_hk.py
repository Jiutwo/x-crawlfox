from typing import Optional
from urllib.parse import quote_plus

from .google import GoogleSearchScraper
from ....models.search_schema import SearchFilter


class GoogleHKSearchScraper(GoogleSearchScraper):
    """Google HK — google.com.hk, same result structure as Google."""

    engine_name = "google-hk"
    home_url = ""
    search_input_selectors = []

    def build_search_url(self, keyword: str, filters: Optional[SearchFilter]) -> str:
        q = self.build_keyword_with_operators(keyword, filters)
        url = f"https://www.google.com.hk/search?q={quote_plus(q)}"
        if filters:
            if filters.time_range:
                tbs = self._time_params.get(filters.time_range)
                if tbs:
                    url += f"&tbs={tbs}"
            if filters.language:
                url += f"&lr=lang_{filters.language}"
        return url
