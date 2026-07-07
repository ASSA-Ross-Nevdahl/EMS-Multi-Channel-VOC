"""Static HTML dashboard.

Self-contained (inline CSS/SVG, no external assets), light/dark aware via
prefers-color-scheme. Palette and mark specs follow the validated reference
data-viz palette: categorical slot 1 (blue) / slot 2 (aqua), text in ink
tokens, thin bars with a 4px rounded data-end, hairline chrome.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from datetime import datetime, timezone

from ..analysis import (
    brand_mentions,
    notable_items,
    source_type_counts,
    tag_counts,
    weekly_volume,
)

CSS = """
:root {
  --surface-1: #fcfcfb;
  --page: #f9f9f7;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --grid: #e1e0d9;
  --baseline: #c3c2b7;
  --border: rgba(11, 11, 11, 0.10);
  --series-1: #2a78d6;  /* blue  — primary / own brands */
  --series-2: #1baf7a;  /* aqua  — competitors */
  --delta-good: #006300;
  --delta-bad: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1: #1a1a19;
    --page: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --baseline: #383835;
    --border: rgba(255, 255, 255, 0.10);
    --series-1: #3987e5;
    --series-2: #199e70;
    --delta-good: #0ca30c;
    --delta-bad: #e66767;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--page);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.5;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 24px 20px 64px; }
header h1 { font-size: 22px; margin: 0 0 2px; }
header p { color: var(--text-secondary); margin: 0 0 24px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
.tile {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
}
.tile .label { color: var(--text-secondary); font-size: 13px; }
.tile .value { font-size: 30px; font-weight: 600; margin-top: 2px; }
.tile .delta { font-size: 13px; margin-top: 2px; }
.delta.up { color: var(--delta-good); }
.delta.down { color: var(--delta-bad); }
.delta.flat { color: var(--text-muted); }
.card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px 20px;
  margin-bottom: 20px;
}
.card h2 { font-size: 15px; margin: 0 0 4px; }
.card .sub { color: var(--text-muted); font-size: 12.5px; margin: 0 0 14px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 760px) { .grid2 { grid-template-columns: 1fr; } }
.barrow { display: grid; grid-template-columns: 180px 1fr; gap: 10px; align-items: center; margin: 7px 0; }
.barrow .name { color: var(--text-secondary); font-size: 13px; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.track { display: flex; align-items: center; gap: 8px; border-left: 1px solid var(--baseline); padding-left: 1px; min-height: 16px; }
.bar { height: 16px; border-radius: 0 4px 4px 0; min-width: 2px; }
.bar.s1 { background: var(--series-1); }
.bar.s2 { background: var(--series-2); }
.val { font-size: 13px; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.legend { display: flex; gap: 16px; margin: 0 0 12px; font-size: 13px; color: var(--text-secondary); }
.legend .key { display: inline-flex; align-items: center; gap: 6px; }
.swatch { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.swatch.s1 { background: var(--series-1); }
.swatch.s2 { background: var(--series-2); }
.spark svg { display: block; width: 100%; height: auto; }
table.items { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.items th {
  text-align: left; color: var(--text-muted); font-weight: 500; font-size: 12.5px;
  border-bottom: 1px solid var(--grid); padding: 6px 10px 6px 0;
}
table.items td { border-bottom: 1px solid var(--grid); padding: 8px 10px 8px 0; vertical-align: top; }
table.items td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.items a { color: var(--text-primary); text-decoration: none; border-bottom: 1px solid var(--baseline); }
table.items a:hover { border-bottom-color: var(--series-1); }
.tag { display: inline-block; font-size: 11.5px; color: var(--text-secondary); background: var(--page); border: 1px solid var(--grid); border-radius: 4px; padding: 0 6px; margin: 1px 3px 1px 0; white-space: nowrap; }
.insights { font-size: 14px; }
.insights h2 { font-size: 15px; margin: 16px 0 6px; }
.insights h2:first-child { margin-top: 0; }
.insights ul { margin: 4px 0 12px; padding-left: 20px; }
.insights li { margin: 4px 0; }
.empty { color: var(--text-muted); font-size: 13px; }
footer { color: var(--text-muted); font-size: 12px; margin-top: 8px; }
"""


def render_dashboard(
    current: list[dict],
    previous: list[dict],
    all_items: list[dict],
    days: int,
    insights_md: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    st_now = source_type_counts(current)
    st_prev = source_type_counts(previous)
    brands_now = brand_mentions(current)
    brands_prev = brand_mentions(previous)
    comp_total_now = sum(brands_now["competitors"].values())
    comp_total_prev = sum(brands_prev["competitors"].values())

    tiles = "".join(
        [
            _tile("Items collected", len(current), len(previous)),
            _tile("Reddit discussions", st_now.get("reddit", 0), st_prev.get("reddit", 0)),
            _tile(
                "Articles & news",
                st_now.get("rss", 0) + st_now.get("web", 0),
                st_prev.get("rss", 0) + st_prev.get("web", 0),
            ),
            _tile("Competitor mentions", comp_total_now, comp_total_prev),
        ]
    )

    categories_chart = _bar_chart(tag_counts(current, "categories"))
    themes_chart = _bar_chart(tag_counts(current, "themes"))
    brand_chart = _brand_chart(brands_now)
    spark = _sparkline(weekly_volume(all_items))
    insights_html = _md_to_html(insights_md) if insights_md else ""
    items_table = _items_table(notable_items(current, limit=20))

    insights_card = (
        f'<section class="card"><h2>Insights (Claude analysis)</h2>'
        f'<p class="sub">Generated from this period’s items — verify before acting.</p>'
        f'<div class="insights">{insights_html}</div></section>'
        if insights_html
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EMS VOC Radar</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>EMS VOC Radar</h1>
  <p>Access control &amp; door hardware — voice of customer for HES · Securitron · Alarm Controls · Adams Rite<br>
  Last {days} days · generated {now:%Y-%m-%d %H:%M} UTC · deltas vs. prior {days} days</p>
</header>

<div class="tiles">{tiles}</div>

{insights_card}

<div class="grid2">
  <section class="card">
    <h2>Mentions by product category</h2>
    <p class="sub">Tagged items this period</p>
    {categories_chart}
  </section>
  <section class="card">
    <h2>Themes</h2>
    <p class="sub">What the conversation is about</p>
    {themes_chart}
  </section>
</div>

<section class="card">
  <h2>Brand share of voice</h2>
  <p class="sub">Mentions across all channels this period</p>
  {brand_chart}
</section>

<section class="card">
  <h2>Collection volume</h2>
  <p class="sub">Items per week, trailing 12 weeks (all sources)</p>
  <div class="spark">{spark}</div>
</section>

<section class="card">
  <h2>Notable items</h2>
  <p class="sub">Highest-engagement discussions and most recent tagged articles</p>
  {items_table}
</section>

<footer>EMS VOC Radar · public sources only (trade press RSS, Reddit public API, competitor news pages) · see reports/digest-latest.md for the text version</footer>
</div>
</body>
</html>
"""


def _tile(label: str, value: int, prev: int) -> str:
    d = value - prev
    cls, arrow = ("up", "▲") if d > 0 else ("down", "▼") if d < 0 else ("flat", "–")
    delta = f"{arrow} {abs(d)}" if d else "– no change"
    return (
        f'<div class="tile"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{value:,}</div>'
        f'<div class="delta {cls}">{delta}</div></div>'
    )


def _bar_chart(counts: Counter, series_cls: str = "s1", max_rows: int = 10) -> str:
    if not counts:
        return '<p class="empty">No tagged mentions this period.</p>'
    top = counts.most_common(max_rows)
    peak = max(c for _, c in top)
    rows = []
    for name, count in top:
        width = max(round(count / peak * 100), 2)
        rows.append(
            f'<div class="barrow"><div class="name" title="{html.escape(name)}">{html.escape(name)}</div>'
            f'<div class="track"><div class="bar {series_cls}" style="width:{width}%" '
            f'title="{html.escape(name)}: {count}"></div>'
            f'<span class="val">{count:,}</span></div></div>'
        )
    return "".join(rows)


def _brand_chart(brands: dict[str, Counter], max_rows: int = 12) -> str:
    """Own brands (blue) and competitors (aqua) on one magnitude scale."""
    combined: list[tuple[str, int, str]] = [
        (name, count, "s1") for name, count in brands["own"].items()
    ] + [(name, count, "s2") for name, count in brands["competitors"].items()]
    if not combined:
        return '<p class="empty">No brand mentions this period.</p>'
    combined.sort(key=lambda t: t[1], reverse=True)
    combined = combined[:max_rows]
    peak = max(c for _, c, _ in combined)
    legend = (
        '<div class="legend">'
        '<span class="key"><span class="swatch s1"></span>EMS brands</span>'
        '<span class="key"><span class="swatch s2"></span>Competitors</span>'
        "</div>"
    )
    rows = []
    for name, count, cls in combined:
        width = max(round(count / peak * 100), 2)
        rows.append(
            f'<div class="barrow"><div class="name" title="{html.escape(name)}">{html.escape(name)}</div>'
            f'<div class="track"><div class="bar {cls}" style="width:{width}%" '
            f'title="{html.escape(name)}: {count}"></div>'
            f'<span class="val">{count:,}</span></div></div>'
        )
    return legend + "".join(rows)


def _sparkline(series: list[tuple[str, int]], width: int = 720, height: int = 64) -> str:
    if not series:
        return '<p class="empty">No history yet.</p>'
    peak = max(v for _, v in series) or 1
    pad_x, pad_y = 6, 8
    step = (width - 2 * pad_x) / max(len(series) - 1, 1)
    pts = []
    for i, (_, v) in enumerate(series):
        x = pad_x + i * step
        y = height - pad_y - (v / peak) * (height - 2 * pad_y)
        pts.append((round(x, 1), round(y, 1)))
    path = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
    ex, ey = pts[-1]
    last_label, last_val = series[-1]
    labels = (
        f'<text x="{pad_x}" y="{height - 1}" fill="var(--text-muted)" font-size="10">{html.escape(series[0][0])}</text>'
        f'<text x="{width - pad_x}" y="{height - 1}" fill="var(--text-muted)" font-size="10" text-anchor="end">{html.escape(last_label)} · {last_val}</text>'
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Weekly item volume, last {len(series)} weeks">'
        f'<path d="{path}" fill="none" stroke="var(--series-1)" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{ex}" cy="{ey}" r="5" fill="var(--series-1)" '
        f'stroke="var(--surface-1)" stroke-width="2"/>'
        f"{labels}</svg>"
    )


def _items_table(items: list[dict]) -> str:
    if not items:
        return '<p class="empty">Nothing tagged this period.</p>'
    rows = []
    for it in items:
        date = (it.get("published") or it.get("collected_at") or "")[:10]
        engagement = (
            f"{it['score']:,} pts · {it.get('num_comments') or 0} com."
            if it.get("score") is not None
            else "—"
        )
        tags = it.get("tags", {})
        tag_html = "".join(
            f'<span class="tag">{html.escape(v)}</span>'
            for key in ("own_brands", "competitors", "categories", "themes")
            for v in tags.get(key, [])
        )
        rows.append(
            "<tr>"
            f'<td><a href="{html.escape(it["url"], quote=True)}">{html.escape(it["title"])}</a>'
            f"<div>{tag_html}</div></td>"
            f"<td>{html.escape(it['source'])}</td>"
            f'<td class="num">{engagement}</td>'
            f'<td class="num">{date}</td>'
            "</tr>"
        )
    return (
        '<table class="items"><thead><tr>'
        "<th>Item</th><th>Source</th><th>Engagement</th><th>Date</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _md_to_html(md: str) -> str:
    """Minimal Markdown renderer for the LLM brief (headings, bullets, bold,
    links, paragraphs). Escapes everything else."""
    out: list[str] = []
    in_list = False
    for raw_line in md.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2>{_inline(m.group(2))}</h2>")
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(m.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2">\1</a>',
        escaped,
    )
    return escaped
