"""
Shared mock factories for search engine scraper unit tests.

All tests replace Playwright Page interactions with MagicMock objects so
no real browser is needed.  Each factory returns a mock element that mimics
the portion of the DOM consumed by a specific engine's extract_results().
"""
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Page helpers
# ---------------------------------------------------------------------------

def page_with_results(items: list) -> MagicMock:
    """Return a mock Page whose locator(...).all() yields *items*."""
    page = MagicMock()
    page.locator.return_value.all.return_value = items
    return page


def page_no_results() -> MagicMock:
    return page_with_results([])


# ---------------------------------------------------------------------------
# Generic item factory
#
# Covers engines whose extract_results() does:
#   link_el = item.locator(LINK_SEL).first   → title + href
#   desc_el = item.locator(DESC_SEL).first   → description
# ---------------------------------------------------------------------------

def make_item(
    link_selector: str,
    desc_selectors: list,
    title: str = "Test Title",
    href: str = "https://example.com",
    desc: str | None = None,
    has_link: bool = True,
) -> MagicMock:
    """
    Build a mock DOM element for engines that obtain title via the same
    <a> element that carries the href.

    Parameters
    ----------
    link_selector : CSS selector string used in item.locator(link_selector)
    desc_selectors : list of CSS selector strings tried for the description
    title : inner text of the link element
    href : href attribute of the link element
    desc : inner text of the description element (None → element has count=0)
    has_link : if False the link element reports count=0 (item will be skipped)
    """
    link = MagicMock()
    link.count.return_value = 1 if has_link else 0
    link.inner_text.return_value = title
    link.get_attribute.return_value = href

    desc_el = MagicMock()
    desc_el.count.return_value = 1 if desc else 0
    desc_el.inner_text.return_value = desc or ""

    empty = MagicMock()
    empty.count.return_value = 0

    def _locator(selector):
        m = MagicMock()
        if selector == link_selector:
            m.first = link
        elif selector in desc_selectors:
            m.first = desc_el
        else:
            m.first = empty
        return m

    item = MagicMock()
    item.locator.side_effect = _locator
    return item


# ---------------------------------------------------------------------------
# Title-element factory
#
# Covers engines whose extract_results() does:
#   link_el = item.locator(LINK_SEL).first   → href only
#   title_el = item.locator(TITLE_SEL).first → title text
#   desc_el = item.locator(DESC_SEL).first   → description
# ---------------------------------------------------------------------------

def make_item_with_title_el(
    link_selector: str,
    title_selectors: list,
    desc_selectors: list,
    title: str = "Test Title",
    href: str = "https://example.com",
    desc: str | None = None,
    has_link: bool = True,
) -> MagicMock:
    """
    Build a mock DOM element for engines that carry the title in a separate
    element (e.g. Brave, Toutiao, Qwant).
    """
    link = MagicMock()
    link.count.return_value = 1 if has_link else 0
    link.inner_text.return_value = title   # fallback when no title_el
    link.get_attribute.return_value = href

    title_el = MagicMock()
    title_el.count.return_value = 1
    title_el.inner_text.return_value = title

    desc_el = MagicMock()
    desc_el.count.return_value = 1 if desc else 0
    desc_el.inner_text.return_value = desc or ""

    empty = MagicMock()
    empty.count.return_value = 0

    def _locator(selector):
        m = MagicMock()
        if selector == link_selector:
            m.first = link
        elif selector in title_selectors:
            m.first = title_el
        elif selector in desc_selectors:
            m.first = desc_el
        else:
            m.first = empty
        return m

    item = MagicMock()
    item.locator.side_effect = _locator
    return item


# ---------------------------------------------------------------------------
# WolframAlpha page factory (HTML-based)
#
# WolframAlpha's extract_results() calls page.content() and parses the
# returned HTML with BeautifulSoup4.  We therefore mock at the page level,
# returning real HTML strings rather than Playwright locator mocks.
# ---------------------------------------------------------------------------

def _wa_pod_html(title: str, content: str | None) -> str:
    """Render one WolframAlpha pod as an HTML fragment."""
    if content is not None:
        escaped = content.replace("&", "&amp;").replace('"', "&quot;")
        img = f'<img alt="{escaped}" src="data:image/gif;base64,abc">'
    else:
        img = ""
    return (
        f'<section tabindex="0">'
        f'<div target="header"><h2><span>{title}</span></h2></div>'
        f"<div>{img}</div>"
        f"</section>"
    )


def make_wa_page(pods: list[dict]) -> MagicMock:
    """Return a mock Page whose content() yields WolframAlpha pod HTML.

    Each dict in *pods* may have:
      - ``title``   (str)       : pod header text
      - ``content`` (str|None)  : img alt text; None → no <img> element
    """
    body = "".join(
        _wa_pod_html(p.get("title", ""), p.get("content"))
        for p in pods
    )
    page = MagicMock()
    page.content.return_value = f"<html><body>{body}</body></html>"
    return page


# ---------------------------------------------------------------------------
# Qwant page factory (HTML-based)
#
# Qwant uses CSS-in-JS class names (unstable) and React rendering.
# extract_results() calls page.content() and uses BeautifulSoup4.
# The result URL lives in the 'domain' attribute of [data-testid="webResult"].
# ---------------------------------------------------------------------------

def _qwant_result_html(title: str, href: str, desc: str | None = None) -> str:
    """Render one Qwant organic result as an HTML fragment."""
    if desc:
        escaped = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        desc_html = f'<div class="ikbiq"><div>{escaped}</div></div>'
    else:
        desc_html = ""
    return (
        # domain attribute carries the result URL
        f'<div domain="{href}" data-testid="webResult">'
        f'<div data-testid="SERVariant-A">'
        # domain section: favicon link + domain-name link + breadcrumbs link
        f'<div><div data-testid="domain">'
        f'<a href="{href}" class="external"><img alt="favicon"></a>'
        f'<a href="{href}" class="external"><div>example.com</div></a>'
        f'<div data-testid="breadcrumbs">'
        f'<a href="{href}" class="external IXeY3 extra"><span>bc</span></a>'
        f'</div>'
        f'</div></div>'
        # content section: title link (single class "external") + description
        f'<div><div>'
        f'<a href="{href}" class="external"><div><span>{title}</span></div></a>'
        f'{desc_html}'
        f'</div></div>'
        f'</div>'
        f'</div>'
    )


def make_qwant_page(results: list[dict]) -> MagicMock:
    """Return a mock Page whose content() yields Qwant webResult HTML.

    Each dict may have:
      - ``title``   (str)       : result title
      - ``href``    (str)       : result URL (also set as domain attribute)
      - ``desc``    (str|None)  : description text; None → no description element
      - ``no_href`` (bool)      : if True, domain attribute is omitted (item skipped)
    """
    parts = []
    for r in results:
        if r.get("no_href"):
            parts.append('<div data-testid="webResult"><span>no-href item</span></div>')
        else:
            parts.append(_qwant_result_html(r["title"], r["href"], r.get("desc")))
    page = MagicMock()
    page.content.return_value = f"<html><body>{''.join(parts)}</body></html>"
    return page


# ---------------------------------------------------------------------------
# Startpage page factory (HTML-based)
#
# extract_results() uses BeautifulSoup on page.content().
# Each result: div.result or article.result  >  h2/h3 > a  +  p (description)
# ---------------------------------------------------------------------------

def _startpage_result_html(title: str, href: str, desc: str | None = None) -> str:
    desc_html = f"<p>{desc}</p>" if desc else ""
    return f'<div class="result"><h2><a href="{href}">{title}</a></h2>{desc_html}</div>'


def make_startpage_page(results: list[dict]) -> MagicMock:
    """Return a mock Page whose content() yields Startpage result HTML.

    Each dict may have:
      - ``title``   (str)
      - ``href``    (str)
      - ``desc``    (str|None)
      - ``no_link`` (bool) : if True, the <a> is omitted (item skipped)
    """
    parts = []
    for r in results:
        if r.get("no_link"):
            parts.append('<div class="result"><h2>No link here</h2></div>')
        else:
            parts.append(_startpage_result_html(r["title"], r["href"], r.get("desc")))
    page = MagicMock()
    page.content.return_value = f"<html><body>{''.join(parts)}</body></html>"
    return page


# ---------------------------------------------------------------------------
# Toutiao page factory (HTML-based)
#
# extract_results() uses BeautifulSoup on page.content().
# Each result: div.result-content[cr-params=JSON]  >  a.l-card-title[href=/search/jump?url=...]
#              + optional div.l-paragraph  (description)
# Real URL decoded from the ?url= query param of the redirect href.
# ---------------------------------------------------------------------------

def _toutiao_result_html(
    title: str,
    real_href: str,
    gid: str = "7000000000001",
    desc: str | None = None,
    no_link: bool = False,
) -> str:
    import json
    from urllib.parse import quote_plus

    cr_params = json.dumps({"gid": gid, "title": title})
    redirect = f"/search/jump?url={quote_plus(real_href)}"
    link_html = f'<a class="l-card-title" href="{redirect}">{title}</a>' if not no_link else ""
    desc_html = f'<div class="l-paragraph">{desc}</div>' if desc else ""
    return f"<div class=\"result-content\" cr-params='{cr_params}'>{link_html}{desc_html}</div>"


def make_toutiao_page(results: list[dict]) -> MagicMock:
    """Return a mock Page whose content() yields Toutiao result HTML.

    Each dict may have:
      - ``title``     (str)
      - ``href``      (str) : the real destination URL (encoded in redirect)
      - ``gid``       (str) : optional group id, default "7000000000001"
      - ``desc``      (str|None)
      - ``no_link``   (bool) : if True, no <a> element → item skipped
    """
    parts = [
        _toutiao_result_html(
            r["title"],
            r.get("href", "https://toutiao.com/group/1/"),
            gid=r.get("gid", "7000000000001"),
            desc=r.get("desc"),
            no_link=r.get("no_link", False),
        )
        for r in results
    ]
    page = MagicMock()
    page.content.return_value = f"<html><body>{''.join(parts)}</body></html>"
    return page


# ---------------------------------------------------------------------------
# Jisilu page factory (HTML-based)
#
# extract_results() uses BeautifulSoup on page.content().
# Each result: div.aw-item  >  div.aw-questoin-content  >  h4 > a  (title+href)
#              + optional span.aw-text-color-999 (description/metadata)
# The first div.aw-item without aw-questoin-content is the promo banner (skipped).
# ---------------------------------------------------------------------------

def _jisilu_result_html(title: str, href: str, desc: str | None = None) -> str:
    desc_html = f'<span class="aw-text-color-999">{desc}</span>' if desc else ""
    return (
        f'<div class="aw-item">'
        f'<div class="aw-questoin-content">'
        f'<h4><a href="{href}">{title}</a></h4>'
        f"{desc_html}"
        f"</div>"
        f"</div>"
    )


def make_jisilu_page(results: list[dict], include_promo: bool = False) -> MagicMock:
    """Return a mock Page whose content() yields Jisilu result HTML.

    Each dict may have:
      - ``title``     (str)
      - ``href``      (str) : absolute or relative path
      - ``desc``      (str|None)
      - ``no_link``   (bool) : if True, h4 has no <a> → item skipped
    """
    parts = []
    if include_promo:
        # Promo banner: div.aw-item without aw-questoin-content (must be skipped)
        parts.append('<div class="aw-item"><span>Promo content</span></div>')
    for r in results:
        if r.get("no_link"):
            parts.append(
                '<div class="aw-item">'
                '<div class="aw-questoin-content"><h4>No link here</h4></div>'
                '</div>'
            )
        else:
            parts.append(_jisilu_result_html(r["title"], r["href"], r.get("desc")))
    page = MagicMock()
    page.content.return_value = f"<html><body>{''.join(parts)}</body></html>"
    return page
