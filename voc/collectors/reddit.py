"""Reddit collector using the public JSON listings (no API key required).

Reddit rate-limits unauthenticated clients; we fetch one listing page per
subreddit/listing pair with a descriptive User-Agent, which is well within
the public allowance for a scheduled job.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from .http import fetch

log = logging.getLogger(__name__)

BODY_CHARS = 3000


def collect_reddit(sources: list[dict]) -> list[dict]:
    items: list[dict] = []
    for src in sources:
        sub = src["subreddit"]
        limit = int(src.get("limit", 100))
        for listing in src.get("listings", ["new"]):
            url = f"https://www.reddit.com/r/{sub}/{listing}.json"
            params = {"limit": min(limit, 100), "raw_json": 1}
            if listing == "top":
                params["t"] = "week"
            try:
                resp = fetch(url, params=params)
                items.extend(_parse_listing(sub, resp.json()))
            except Exception as exc:
                log.warning("Reddit r/%s (%s) failed: %s", sub, listing, exc)
            time.sleep(1)  # be polite between listing fetches
    # de-dupe across listings (a post can be in both `new` and `top`)
    seen: set[str] = set()
    unique = []
    for it in items:
        if it["url"] not in seen:
            seen.add(it["url"])
            unique.append(it)
    return unique


def _parse_listing(subreddit: str, payload: dict) -> list[dict]:
    items = []
    for child in payload.get("data", {}).get("children", []):
        d = child.get("data", {})
        permalink = d.get("permalink")
        title = d.get("title")
        if not permalink or not title:
            continue
        published = datetime.fromtimestamp(
            d.get("created_utc", 0), tz=timezone.utc
        ).isoformat(timespec="seconds")
        items.append(
            {
                "source": f"r/{subreddit}",
                "source_type": "reddit",
                "title": title.strip(),
                "url": f"https://www.reddit.com{permalink}",
                "author": d.get("author"),
                "published": published,
                "body": (d.get("selftext") or "")[:BODY_CHARS],
                "score": d.get("score"),
                "num_comments": d.get("num_comments"),
            }
        )
    return items
