"""RSS/Atom collector using stdlib XML parsing (no feedparser dependency)."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from .http import fetch

log = logging.getLogger(__name__)

ATOM_NS = "{http://www.w3.org/2005/Atom}"
BODY_CHARS = 2000


def collect_rss(sources: list[dict]) -> list[dict]:
    items: list[dict] = []
    for src in sources:
        name, url = src["name"], src["url"]
        try:
            resp = fetch(url)
            items.extend(_parse_feed(name, resp.content))
        except Exception as exc:  # network / parse — skip source, keep run alive
            log.warning("RSS source %r failed: %s", name, exc)
    return items


def _parse_feed(source_name: str, content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    tag = root.tag.lower()
    if tag.endswith("feed"):  # Atom
        entries = root.findall(f"{ATOM_NS}entry")
        parse = _parse_atom_entry
    else:  # RSS 2.0 / 0.9x
        entries = root.findall(".//item")
        parse = _parse_rss_item
    items = []
    for entry in entries:
        item = parse(source_name, entry)
        if item:
            items.append(item)
    return items


def _parse_rss_item(source_name: str, item: ET.Element) -> dict | None:
    title = _text(item, "title")
    link = _text(item, "link")
    if not title or not link:
        return None
    published = _parse_date(_text(item, "pubDate") or _text(item, "date"))
    summary = _text(item, "description") or ""
    author = _text(item, "author") or _text(
        item, "{http://purl.org/dc/elements/1.1/}creator"
    )
    return {
        "source": source_name,
        "source_type": "rss",
        "title": title.strip(),
        "url": link.strip(),
        "author": author,
        "published": published,
        "body": _strip_html(summary)[:BODY_CHARS],
    }


def _parse_atom_entry(source_name: str, entry: ET.Element) -> dict | None:
    title = _text(entry, f"{ATOM_NS}title")
    link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
    if link_el is None:
        link_el = entry.find(f"{ATOM_NS}link")
    link = link_el.get("href") if link_el is not None else None
    if not title or not link:
        return None
    published = _parse_date(
        _text(entry, f"{ATOM_NS}published") or _text(entry, f"{ATOM_NS}updated")
    )
    summary = _text(entry, f"{ATOM_NS}summary") or _text(entry, f"{ATOM_NS}content") or ""
    author = _text(entry, f"{ATOM_NS}author/{ATOM_NS}name")
    return {
        "source": source_name,
        "source_type": "rss",
        "title": title.strip(),
        "url": link.strip(),
        "author": author,
        "published": published,
        "body": _strip_html(summary)[:BODY_CHARS],
    }


def _text(el: ET.Element, path: str) -> str | None:
    found = el.find(path)
    return found.text if found is not None and found.text else None


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    dt = None
    try:  # RFC 2822 (RSS pubDate)
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:  # ISO 8601 (Atom)
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
