"""Generic web-page collector for competitor news/press pages.

Each source config provides a URL and a CSS selector matching headline
anchor elements. We record the link text as the title. Publication dates
are usually not machine-readable on these pages, so items fall back to
their collection date for windowing.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http import fetch

log = logging.getLogger(__name__)

MAX_ITEMS_PER_PAGE = 30
MIN_TITLE_CHARS = 15  # skip nav links like "News" or "Read more"


def collect_web(sources: list[dict]) -> list[dict]:
    items: list[dict] = []
    for src in sources:
        name, url = src["name"], src["url"]
        selector = src.get("item_selector", "a")
        try:
            resp = fetch(url)
            items.extend(_parse_page(name, url, resp.text, selector))
        except Exception as exc:
            log.warning("Web source %r failed: %s", name, exc)
    return items


def _parse_page(name: str, page_url: str, html: str, selector: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen: set[str] = set()
    for anchor in soup.select(selector):
        href = anchor.get("href")
        title = anchor.get_text(" ", strip=True)
        if not href or len(title) < MIN_TITLE_CHARS:
            continue
        url = urljoin(page_url, href)
        if url in seen or url.rstrip("/") == page_url.rstrip("/"):
            continue
        seen.add(url)
        items.append(
            {
                "source": name,
                "source_type": "web",
                "title": title,
                "url": url,
                "author": None,
                "published": None,  # falls back to collected_at in queries
                "body": None,
            }
        )
        if len(items) >= MAX_ITEMS_PER_PAGE:
            break
    return items
