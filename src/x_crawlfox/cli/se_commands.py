from typing import Optional
import typer
from loguru import logger

from .utils import save_items, handle_error
from ..core.browser import BrowserManager
from ..models.search_schema import SearchMode, TimeRange, SearchFilter
from ..scrapers.search.engines.baidu import BaiduSearchScraper
from ..scrapers.search.engines.google import GoogleSearchScraper
from ..scrapers.search.engines.bing import BingSearchScraper

se_app = typer.Typer(help="Search engine scraping commands (Baidu / Google / Bing)")

_ENGINE_MAP = {
    "baidu":  BaiduSearchScraper,
    "google": GoogleSearchScraper,
    "bing":   BingSearchScraper,
}


def _build_filters(
    time_range: Optional[TimeRange],
    site: Optional[str],
    filetype: Optional[str],
    exact_phrase: Optional[str],
) -> SearchFilter:
    return SearchFilter(
        time_range=time_range,
        site=site,
        filetype=filetype,
        exact_phrase=exact_phrase,
    )


@se_app.command()
def search(
    keyword: str = typer.Argument(..., help="Search keyword"),
    engine: str = typer.Option("baidu", help=f"Search engine: {' | '.join(_ENGINE_MAP)}"),
    mode: SearchMode = typer.Option(SearchMode.FAST, help="simulate: human-like input  |  fast: direct URL"),
    max_results: int = typer.Option(10, help="Maximum number of results to return"),
    time_range: Optional[TimeRange] = typer.Option(None, help="Time filter: hour|day|week|month|year"),
    site: Optional[str] = typer.Option(None, help="Restrict results to a domain, e.g. github.com"),
    filetype: Optional[str] = typer.Option(None, help="File-type filter, e.g. pdf"),
    exact_phrase: Optional[str] = typer.Option(None, help="Require an exact phrase in results"),
    output: str = typer.Option("output", "--output", "-o", help="Output directory"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Headless browser mode"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address"),
):
    """
    Scrape search results from a single engine.

    Examples:
      x-crawlfox se search "LangGraph" --engine baidu --mode fast --time-range week
      x-crawlfox se search "python async" --engine google --site github.com
    """
    engine = engine.lower()
    if engine not in _ENGINE_MAP:
        logger.error(f"Unknown engine '{engine}'. Available: {', '.join(_ENGINE_MAP)}")
        raise typer.Exit(1)

    filters = _build_filters(time_range, site, filetype, exact_phrase)

    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            page = context.new_page()
            scraper = _ENGINE_MAP[engine](page)
            items = scraper.scrape(keyword=keyword, mode=mode, filters=filters, max_results=max_results)
            if items:
                safe_kw = keyword.replace(" ", "_")[:40]
                save_items(items, f"se_{engine}_{safe_kw}", output_dir=output)
            else:
                logger.warning(f"No results found for '{keyword}' on {engine}.")
    except Exception as e:
        handle_error(e)


@se_app.command()
def multi(
    keyword: str = typer.Argument(..., help="Search keyword"),
    engines: str = typer.Option(
        ",".join(_ENGINE_MAP),
        help="Comma-separated list of engines to query",
    ),
    mode: SearchMode = typer.Option(SearchMode.FAST, help="simulate | fast  (fast is default for multi)"),
    max_results: int = typer.Option(10, help="Maximum results per engine"),
    time_range: Optional[TimeRange] = typer.Option(None, help="Time filter: hour|day|week|month|year"),
    site: Optional[str] = typer.Option(None, help="Restrict results to a domain"),
    filetype: Optional[str] = typer.Option(None, help="File-type filter"),
    exact_phrase: Optional[str] = typer.Option(None, help="Require an exact phrase"),
    output: str = typer.Option("output", "--output", "-o", help="Output directory"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Headless browser mode"),
    proxy: Optional[str] = typer.Option(None, help="Proxy server address"),
):
    """
    Scrape the same keyword across multiple search engines and save all results.

    Examples:
      x-crawlfox se multi "AI Agent" --engines baidu,google,bing --mode fast
      x-crawlfox se multi "rust async" --engines google,bing --time-range month
    """
    engine_list = [e.strip().lower() for e in engines.split(",") if e.strip()]
    invalid = [e for e in engine_list if e not in _ENGINE_MAP]
    if invalid:
        logger.error(f"Unknown engines: {invalid}. Available: {', '.join(_ENGINE_MAP)}")
        raise typer.Exit(1)

    filters = _build_filters(time_range, site, filetype, exact_phrase)
    all_items = []

    try:
        with BrowserManager(headless=headless, proxy=proxy) as context:
            for engine_name in engine_list:
                logger.info(f">>> [{engine_name}] Searching '{keyword}'...")
                page = context.new_page()
                try:
                    scraper = _ENGINE_MAP[engine_name](page)
                    items = scraper.scrape(keyword=keyword, mode=mode, filters=filters, max_results=max_results)
                    all_items.extend(items)
                    logger.info(f"[{engine_name}] {len(items)} results collected")
                except Exception as e:
                    logger.error(f"[{engine_name}] Failed: {e}")
                finally:
                    page.close()

        if all_items:
            safe_kw = keyword.replace(" ", "_")[:40]
            save_items(all_items, f"se_multi_{safe_kw}", output_dir=output)
        else:
            logger.warning(f"No results found for '{keyword}' across engines: {engine_list}")
    except Exception as e:
        handle_error(e)
