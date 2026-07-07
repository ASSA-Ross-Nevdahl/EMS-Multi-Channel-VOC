"""Reddit collector.

Preferred path: Reddit's OAuth API with an app-only token — create a free
"script" app at https://www.reddit.com/prefs/apps and set REDDIT_CLIENT_ID
and REDDIT_CLIENT_SECRET. This is required from cloud/CI runners (GitHub
Actions), whose IPs Reddit blocks for unauthenticated requests.

Fallback: the public JSON listings with a descriptive User-Agent, which
work from residential networks without credentials.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

from .http import USER_AGENT, fetch

log = logging.getLogger(__name__)

BODY_CHARS = 3000


def _oauth_token() -> str | None:
    """App-only OAuth token via client_credentials, if creds are configured."""
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (client_id and client_secret):
        return None
    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as exc:
        log.warning("Reddit OAuth token request failed: %s", exc)
        return None


def collect_reddit(sources: list[dict]) -> list[dict]:
    token = _oauth_token()
    if token:
        base, headers = "https://oauth.reddit.com", {"Authorization": f"Bearer {token}"}
        log.info("using Reddit OAuth API")
    else:
        base, headers = "https://www.reddit.com", {}
        log.info("no REDDIT_CLIENT_ID/SECRET set; using public Reddit JSON "
                 "(blocked from cloud/CI IPs — set credentials for GitHub Actions)")

    items: list[dict] = []
    for src in sources:
        sub = src["subreddit"]
        limit = int(src.get("limit", 100))
        for listing in src.get("listings", ["new"]):
            url = f"{base}/r/{sub}/{listing}.json"
            params = {"limit": min(limit, 100), "raw_json": 1}
            if listing == "top":
                params["t"] = "week"
            try:
                resp = fetch(url, params=params, headers=headers)
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
