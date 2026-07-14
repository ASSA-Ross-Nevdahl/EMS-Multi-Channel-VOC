"""Static HTML dashboard.

Self-contained (inline CSS/SVG, no external assets), light/dark aware via
prefers-color-scheme. Palette and mark specs follow the validated reference
data-viz palette: categorical slot 1 (blue) / slot 2 (aqua), text in ink
tokens, thin bars with a 4px rounded data-end, hairline chrome.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from ..analysis import (
    brand_mentions,
    news_items,
    news_type_counts,
    notable_items,
    weekly_volume,
)
from ..classify import news_type_of

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
.pill { font-size: 11px; font-weight: 500; border-radius: 10px; padding: 1px 9px; vertical-align: middle; margin-left: 6px; }
.pill.s1 { background: var(--series-1); color: #fff; }
.pill.muted { background: var(--page); color: var(--text-muted); border: 1px solid var(--grid); }
.drill-row { cursor: pointer; border-radius: 6px; }
.drill-row:hover { background: var(--page); }
.drill-row:focus-visible { outline: 2px solid var(--series-1); outline-offset: 1px; }
.drill-row[aria-expanded="true"] .name { color: var(--text-primary); font-weight: 600; }
.caret { color: var(--text-muted); font-size: 10px; margin-left: 4px; display: inline-block; transition: transform .12s ease; }
.drill-row[aria-expanded="true"] .caret { transform: rotate(90deg); }
.drill-panel { margin: 0 0 10px 0; padding: 6px 12px; border-left: 2px solid var(--series-1); background: var(--page); border-radius: 0 6px 6px 0; }
.drill-item { display: flex; align-items: baseline; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--grid); font-size: 13px; }
.drill-item:last-child { border-bottom: 0; }
.drill-item a { color: var(--text-primary); text-decoration: none; border-bottom: 1px solid var(--baseline); }
.drill-item a:hover { border-bottom-color: var(--series-1); }
.di-meta { color: var(--text-muted); font-size: 12px; margin-left: auto; white-space: nowrap; padding-left: 12px; font-variant-numeric: tabular-nums; }
.nt-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: 0 0 auto; align-self: center; }
.nt-dot.product { background: var(--series-1); }
.nt-dot.business { background: var(--text-muted); }
.di-more { color: var(--text-muted); font-size: 12px; padding-top: 6px; }
.scope-toggle { display: flex; align-items: center; gap: 8px; margin: 0 0 18px; flex-wrap: wrap; }
.scope-label { color: var(--text-secondary); font-size: 13px; }
.scope-btn { font: inherit; font-size: 13px; color: var(--text-secondary); background: var(--surface-1); border: 1px solid var(--border); border-radius: 6px; padding: 4px 12px; cursor: pointer; }
.scope-btn:hover { color: var(--text-primary); }
.scope-btn.active { background: var(--series-1); color: #fff; border-color: var(--series-1); }
.scope-btn:focus-visible { outline: 2px solid var(--series-1); outline-offset: 2px; }
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
    brands_now = brand_mentions(current)
    brands_prev = brand_mentions(previous)
    comp_total_now = sum(brands_now["competitors"].values())
    comp_total_prev = sum(brands_prev["competitors"].values())
    nt_now = news_type_counts(current)
    nt_prev = news_type_counts(previous)

    tiles = "".join(
        [
            _tile("Items collected", len(current), len(previous)),
            _tile("Product-level news", nt_now.get("Product", 0),
                  nt_prev.get("Product", 0), accent="s1"),
            _tile("Business-level news", nt_now.get("Business", 0),
                  nt_prev.get("Business", 0)),
            _tile("Competitor mentions", comp_total_now, comp_total_prev),
        ]
    )

    # "Product-level only" view for the toggle: drop business-noise items so
    # the charts reflect roadmap-relevant coverage, not stock/M&A volume.
    product_only = [it for it in current if news_type_of(it) == "Product"]
    NO_PROD = "No product-level mentions this period."

    categories_chart = _scoped_chart(
        _drill_bar_chart(current, "categories", "cat"),
        _drill_bar_chart(product_only, "categories", "catp", empty_msg=NO_PROD),
    )
    themes_chart = _scoped_chart(
        _drill_bar_chart(current, "themes", "theme"),
        _drill_bar_chart(product_only, "themes", "themep", empty_msg=NO_PROD),
    )
    brand_chart = _scoped_chart(
        _brand_chart(current, prefix="brand"),
        _brand_chart(product_only, prefix="brandp", empty_msg=NO_PROD),
    )
    spark = _sparkline(weekly_volume(all_items))
    insights_html = _md_to_html(insights_md) if insights_md else ""
    product_table = _items_table(news_items(current, "Product", limit=25))
    business_table = _items_table(news_items(current, "Business", limit=20))
    reddit_notable = [it for it in notable_items(current, limit=8)
                      if it["source_type"] == "reddit"]
    reddit_section = (
        '<section class="card"><h2>Voice of the field</h2>'
        '<p class="sub">Top installer/integrator discussion this period</p>'
        f"{_items_table(reddit_notable)}</section>"
        if reddit_notable
        else ""
    )

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

<div class="scope-toggle" role="group" aria-label="Chart scope">
  <span class="scope-label">Category, theme &amp; brand charts:</span>
  <button type="button" class="scope-btn active" data-scope="all" aria-pressed="true">All news</button>
  <button type="button" class="scope-btn" data-scope="product" aria-pressed="false">Product-level only</button>
</div>

<div class="grid2">
  <section class="card">
    <h2>Mentions by product category</h2>
    <p class="sub">Tagged items this period · click a bar to see the stories</p>
    {categories_chart}
  </section>
  <section class="card">
    <h2>Themes</h2>
    <p class="sub">What the conversation is about · click a bar to see the stories</p>
    {themes_chart}
  </section>
</div>

<section class="card">
  <h2>Brand share of voice</h2>
  <p class="sub">Mentions across all channels this period · click a bar to see the stories</p>
  {brand_chart}
</section>

<section class="card">
  <h2>Collection volume</h2>
  <p class="sub">Items per week, trailing 12 weeks (all sources)</p>
  <div class="spark">{spark}</div>
</section>

<section class="card">
  <h2>Product-level news <span class="pill s1">roadmap signal</span></h2>
  <p class="sub">New/updated products, features, specs, certifications, recalls — most recent first</p>
  {product_table}
</section>

<section class="card">
  <h2>Business-level news <span class="pill muted">context</span></h2>
  <p class="sub">M&amp;A, leadership, financials, channel, expansion, awards — background, not the headline</p>
  {business_table}
</section>

{reddit_section}

<footer>EMS VOC Radar · public sources only (trade press RSS, Reddit public API, competitor news pages) · see reports/digest-latest.md for the text version</footer>
</div>
<script>
(function () {{
  function toggle(row) {{
    var panel = document.getElementById(row.getAttribute('data-target'));
    if (!panel) return;
    var isOpen = !panel.hasAttribute('hidden');
    var card = row.closest('.card');
    // accordion: one open panel per card
    card.querySelectorAll('.drill-panel').forEach(function (p) {{ p.setAttribute('hidden', ''); }});
    card.querySelectorAll('.drill-row').forEach(function (r) {{ r.setAttribute('aria-expanded', 'false'); }});
    if (!isOpen) {{
      panel.removeAttribute('hidden');
      row.setAttribute('aria-expanded', 'true');
    }}
  }}
  document.querySelectorAll('.drill-row').forEach(function (row) {{
    row.addEventListener('click', function () {{ toggle(row); }});
    row.addEventListener('keydown', function (e) {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); toggle(row); }}
    }});
  }});

  function setScope(scope) {{
    document.querySelectorAll('.chart-scope').forEach(function (el) {{
      if (el.getAttribute('data-scope') === scope) el.removeAttribute('hidden');
      else el.setAttribute('hidden', '');
    }});
    document.querySelectorAll('.scope-btn').forEach(function (b) {{
      var on = b.getAttribute('data-scope') === scope;
      b.classList.toggle('active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    }});
    // collapse any open drill panels so the two scopes don't cross over
    document.querySelectorAll('.drill-panel').forEach(function (p) {{ p.setAttribute('hidden', ''); }});
    document.querySelectorAll('.drill-row').forEach(function (r) {{ r.setAttribute('aria-expanded', 'false'); }});
  }}
  document.querySelectorAll('.scope-btn').forEach(function (b) {{
    b.addEventListener('click', function () {{ setScope(b.getAttribute('data-scope')); }});
  }});
}})();
</script>
</body>
</html>
"""


def _tile(label: str, value: int, prev: int, accent: str | None = None) -> str:
    d = value - prev
    cls, arrow = ("up", "▲") if d > 0 else ("down", "▼") if d < 0 else ("flat", "–")
    delta = f"{arrow} {abs(d)}" if d else "– no change"
    style = f' style="border-left:3px solid var(--series-1)"' if accent == "s1" else ""
    return (
        f'<div class="tile"{style}><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{value:,}</div>'
        f'<div class="delta {cls}">{delta}</div></div>'
    )


def _drill_row(name: str, count: int, width: int, cls: str, pid: str,
               items: list[dict]) -> str:
    """One clickable bar row plus its (initially hidden) items panel."""
    return (
        f'<div class="barrow drill-row" role="button" tabindex="0" '
        f'aria-expanded="false" aria-controls="{pid}" data-target="{pid}">'
        f'<div class="name" title="{html.escape(name)}">{html.escape(name)}</div>'
        f'<div class="track"><div class="bar {cls}" style="width:{width}%"></div>'
        f'<span class="val">{count:,}</span>'
        f'<span class="caret" aria-hidden="true">&#9656;</span></div></div>'
        f'<div class="drill-panel" id="{pid}" role="region" '
        f'aria-label="{html.escape(name)} items" hidden>{_drill_items(items)}</div>'
    )


def _drill_bar_chart(items: list[dict], tag_key: str, prefix: str,
                     max_rows: int = 10,
                     empty_msg: str = "No tagged mentions this period.") -> str:
    """Bar chart whose bars expand to list the items behind each count."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        for name in it.get("tags", {}).get(tag_key, []):
            groups.setdefault(name, []).append(it)
    if not groups:
        return f'<p class="empty">{html.escape(empty_msg)}</p>'
    ordered = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)[:max_rows]
    peak = max(len(v) for _, v in ordered)
    rows = [
        _drill_row(name, len(its), max(round(len(its) / peak * 100), 2),
                   "s1", f"{prefix}-{i}", its)
        for i, (name, its) in enumerate(ordered)
    ]
    return f'<div class="drill">{"".join(rows)}</div>'


def _brand_chart(items: list[dict], prefix: str = "brand", max_rows: int = 12,
                 empty_msg: str = "No brand mentions this period.") -> str:
    """Own brands (blue) and competitors (aqua) on one magnitude scale, each
    bar expandable to the stories mentioning that brand."""
    own: dict[str, list[dict]] = {}
    comp: dict[str, list[dict]] = {}
    for it in items:
        tags = it.get("tags", {})
        for name in tags.get("own_brands", []):
            own.setdefault(name, []).append(it)
        for name in tags.get("competitors", []):
            comp.setdefault(name, []).append(it)
    combined = (
        [(name, its, "s1") for name, its in own.items()]
        + [(name, its, "s2") for name, its in comp.items()]
    )
    if not combined:
        return f'<p class="empty">{html.escape(empty_msg)}</p>'
    combined.sort(key=lambda t: len(t[1]), reverse=True)
    combined = combined[:max_rows]
    peak = max(len(its) for _, its, _ in combined)
    legend = (
        '<div class="legend">'
        '<span class="key"><span class="swatch s1"></span>EMS brands</span>'
        '<span class="key"><span class="swatch s2"></span>Competitors</span>'
        "</div>"
    )
    rows = [
        _drill_row(name, len(its), max(round(len(its) / peak * 100), 2),
                   cls, f"{prefix}-{i}", its)
        for i, (name, its, cls) in enumerate(combined)
    ]
    return legend + f'<div class="drill">{"".join(rows)}</div>'


def _scoped_chart(all_html: str, product_html: str) -> str:
    """Wrap the all-news and product-only variants of a chart; the toggle
    controls which is visible."""
    return (
        f'<div class="chart-scope" data-scope="all">{all_html}</div>'
        f'<div class="chart-scope" data-scope="product" hidden>{product_html}</div>'
    )


def _drill_items(items: list[dict], limit: int = 40) -> str:
    """Compact linked list of the stories behind a bar, most recent first,
    each prefixed with a product/business dot when classified."""
    ordered = sorted(
        items,
        key=lambda it: it.get("published") or it.get("collected_at") or "",
        reverse=True,
    )
    rows = []
    for it in ordered[:limit]:
        date = (it.get("published") or it.get("collected_at") or "")[:10]
        nt = news_type_of(it)
        dot = ""
        if nt in ("Product", "Business"):
            cls = "product" if nt == "Product" else "business"
            dot = f'<span class="nt-dot {cls}" title="{nt}-level"></span>'
        meta = " · ".join(x for x in (it["source"], date) if x)
        rows.append(
            f'<div class="drill-item">{dot}'
            f'<a href="{html.escape(it["url"], quote=True)}">{html.escape(it["title"])}</a>'
            f'<span class="di-meta">{html.escape(meta)}</span></div>'
        )
    if len(ordered) > limit:
        rows.append(f'<div class="di-more">+{len(ordered) - limit} more</div>')
    return "".join(rows)


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
    # Only show the engagement column when at least one row has engagement
    # (news articles have none; Reddit discussions do).
    show_engagement = any(it.get("score") is not None for it in items)
    rows = []
    for it in items:
        date = (it.get("published") or it.get("collected_at") or "")[:10]
        tags = it.get("tags", {})
        # news_type is conveyed by the section the row lives in, so it's
        # omitted here to avoid a redundant chip on every row.
        tag_html = "".join(
            f'<span class="tag">{html.escape(v)}</span>'
            for key in ("own_brands", "competitors", "categories", "themes")
            for v in tags.get(key, [])
        )
        engagement_cell = ""
        if show_engagement:
            eng = (
                f"{it['score']:,} pts · {it.get('num_comments') or 0} com."
                if it.get("score") is not None
                else "—"
            )
            engagement_cell = f'<td class="num">{eng}</td>'
        rows.append(
            "<tr>"
            f'<td><a href="{html.escape(it["url"], quote=True)}">{html.escape(it["title"])}</a>'
            f"<div>{tag_html}</div></td>"
            f"<td>{html.escape(it['source'])}</td>"
            f"{engagement_cell}"
            f'<td class="num">{date}</td>'
            "</tr>"
        )
    eng_header = "<th>Engagement</th>" if show_engagement else ""
    return (
        '<table class="items"><thead><tr>'
        f"<th>Item</th><th>Source</th>{eng_header}<th>Date</th>"
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
