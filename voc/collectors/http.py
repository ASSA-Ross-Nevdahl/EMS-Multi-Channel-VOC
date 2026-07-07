"""Shared HTTP fetching with a polite User-Agent and retries."""

from __future__ import annotations

import time

import requests

USER_AGENT = (
    "ems-voc-radar/0.1 (market research aggregator; contact repository owner)"
)
TIMEOUT = 20
RETRIES = 2


def fetch(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    last_exc: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT, **kwargs)
            if resp.status_code == 429 and attempt < RETRIES:
                time.sleep(int(resp.headers.get("Retry-After", 5)))
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
    raise last_exc  # type: ignore[misc]
