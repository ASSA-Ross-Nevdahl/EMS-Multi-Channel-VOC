"""Aggregation over tagged items: period counts, deltas, weekly trend,
notable items."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone


def period_bounds(days: int, now: datetime | None = None) -> tuple[str, str, str]:
    """Return (prev_start, current_start, now) as ISO strings for a window of
    `days` and the equal-length window preceding it."""
    now = now or datetime.now(timezone.utc)
    current_start = now - timedelta(days=days)
    prev_start = now - timedelta(days=2 * days)
    fmt = lambda d: d.isoformat(timespec="seconds")  # noqa: E731
    return fmt(prev_start), fmt(current_start), fmt(now)


def tag_counts(items: list[dict], tag_key: str) -> Counter:
    c: Counter = Counter()
    for it in items:
        for value in it.get("tags", {}).get(tag_key, []):
            c[value] += 1
    return c


def source_type_counts(items: list[dict]) -> Counter:
    return Counter(it["source_type"] for it in items)


def weekly_volume(items: list[dict], weeks: int = 12,
                  now: datetime | None = None) -> list[tuple[str, int]]:
    """Item count per ISO week for the trailing `weeks` weeks, oldest first."""
    now = now or datetime.now(timezone.utc)
    buckets: Counter = Counter()
    for it in items:
        raw = it.get("published") or it.get("collected_at")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        iso = dt.isocalendar()
        buckets[f"{iso.year}-W{iso.week:02d}"] += 1
    out = []
    for i in range(weeks - 1, -1, -1):
        dt = now - timedelta(weeks=i)
        iso = dt.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        out.append((key, buckets.get(key, 0)))
    return out


def notable_items(items: list[dict], limit: int = 15) -> list[dict]:
    """Rank items for the digest: tagged reddit discussion by engagement
    first, then tagged articles by recency."""

    def is_tagged(it: dict) -> bool:
        return bool(it.get("tags"))

    reddit = sorted(
        (it for it in items if it["source_type"] == "reddit" and is_tagged(it)),
        key=lambda it: (it.get("score") or 0) + 2 * (it.get("num_comments") or 0),
        reverse=True,
    )
    articles = sorted(
        (it for it in items if it["source_type"] != "reddit" and is_tagged(it)),
        key=lambda it: it.get("published") or it.get("collected_at") or "",
        reverse=True,
    )
    half = max(limit // 2, 1)
    picked = reddit[:half] + articles[: limit - min(len(reddit), half)]
    return picked[:limit]


def brand_mentions(items: list[dict]) -> dict[str, Counter]:
    return {
        "own": tag_counts(items, "own_brands"),
        "competitors": tag_counts(items, "competitors"),
        "assa_abloy_other": tag_counts(items, "assa_abloy_other"),
    }
