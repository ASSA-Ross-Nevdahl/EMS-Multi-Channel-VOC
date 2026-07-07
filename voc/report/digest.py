"""Markdown digest for product managers."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from ..analysis import (
    brand_mentions,
    notable_items,
    source_type_counts,
    tag_counts,
)


def render_digest(
    current: list[dict],
    previous: list[dict],
    days: int,
    insights_md: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    st = source_type_counts(current)
    lines = [
        "# EMS VOC Radar — digest",
        "",
        f"*Period: last {days} days, generated {now:%Y-%m-%d %H:%M} UTC*",
        "",
        f"**{len(current)}** items collected "
        f"({_delta(len(current), len(previous))} vs. prior {days} days): "
        f"{st.get('reddit', 0)} Reddit discussions, "
        f"{st.get('rss', 0)} trade-press articles, "
        f"{st.get('web', 0)} competitor page items.",
        "",
    ]

    if insights_md:
        lines += ["---", "", "# Insights (Claude analysis)", "", insights_md, "", "---", ""]

    lines += _count_section(
        "Mentions by product category",
        tag_counts(current, "categories"),
        tag_counts(previous, "categories"),
    )

    brands_now = brand_mentions(current)
    brands_prev = brand_mentions(previous)
    lines += _count_section(
        "Own-brand mentions (HES / Securitron / Alarm Controls / Adams Rite)",
        brands_now["own"],
        brands_prev["own"],
    )
    lines += _count_section(
        "Competitor mentions", brands_now["competitors"], brands_prev["competitors"]
    )
    lines += _count_section(
        "Themes", tag_counts(current, "themes"), tag_counts(previous, "themes")
    )

    lines += ["## Notable items", ""]
    for it in notable_items(current):
        meta = [it["source"]]
        if it.get("score") is not None:
            meta.append(f"{it['score']} pts / {it.get('num_comments') or 0} comments")
        date = (it.get("published") or it.get("collected_at") or "")[:10]
        if date:
            meta.append(date)
        tags = it.get("tags", {})
        tag_str = "; ".join(
            ", ".join(v) for k, v in sorted(tags.items()) if v
        )
        lines.append(f"- [{it['title']}]({it['url']}) — {' · '.join(meta)}")
        if tag_str:
            lines.append(f"  - tags: {tag_str}")
    lines.append("")
    return "\n".join(lines)


def _count_section(title: str, now: Counter, prev: Counter) -> list[str]:
    lines = [f"## {title}", ""]
    if not now:
        return lines + ["_No mentions this period._", ""]
    lines += ["| | mentions | vs. prior |", "|---|---:|---:|"]
    for name, count in now.most_common():
        lines.append(f"| {name} | {count} | {_delta(count, prev.get(name, 0))} |")
    return lines + [""]


def _delta(now: int, prev: int) -> str:
    d = now - prev
    return f"+{d}" if d > 0 else str(d)
