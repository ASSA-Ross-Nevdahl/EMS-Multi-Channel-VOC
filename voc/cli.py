"""Command-line interface.

    python -m voc collect            # fetch all sources into the database
    python -m voc analyze            # (re-)tag every stored item
    python -m voc report             # write digest + dashboard to reports/
    python -m voc run                # collect + analyze + report

Common options: --days N, --config DIR, --db PATH, --out DIR, --no-llm
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db as dbm
from . import llm
from .analysis import news_items, notable_items, period_bounds
from .classify import LABELS, NewsClassifier
from .collectors import collect_reddit, collect_rss, collect_web
from .config import DEFAULT_CONFIG_DIR, load_sources, load_taxonomy
from .report import render_dashboard, render_digest
from .tagging import Tagger

log = logging.getLogger("voc")

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "reports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="voc", description=__doc__)
    parser.add_argument("command", choices=["collect", "analyze", "report", "run"])
    parser.add_argument("--days", type=int, default=7,
                        help="reporting window in days (default 7)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_DIR,
                        help="config directory containing sources.yaml/taxonomy.yaml")
    parser.add_argument("--db", type=Path, default=None, help="SQLite db path")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                        help="output directory for reports")
    parser.add_argument("--no-llm", action="store_true",
                        help="skip the Claude insight brief even if credentials exist")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    conn = dbm.connect(args.db)
    try:
        if args.command in ("collect", "run"):
            cmd_collect(conn, args)
        if args.command in ("analyze", "run"):
            cmd_analyze(conn, args)
        if args.command in ("report", "run"):
            cmd_report(conn, args)
    finally:
        conn.close()
    return 0


def _tag_and_classify(it: dict, tagger: Tagger, classifier: NewsClassifier) -> dict:
    tags = tagger.tag(it["title"], it.get("body"))
    result = classifier.classify(
        it["title"], it.get("body"), tags, it["source_type"]
    )
    if result is not None:
        tags["news_type"] = [LABELS[result[0]]]
    return tags


def cmd_collect(conn, args) -> None:
    sources = load_sources(args.config)
    taxonomy = load_taxonomy(args.config)
    tagger = Tagger(taxonomy)
    classifier = NewsClassifier(taxonomy)

    feeds = (
        sources["rss"]
        + sources["competitor_news_rss"]
        + sources["own_brand_news_rss"]
    )
    items: list[dict] = []
    log.info("collecting %d RSS feeds…", len(feeds))
    items += collect_rss(feeds)
    log.info("collecting %d subreddits…", len(sources["reddit"]))
    items += collect_reddit(sources["reddit"])
    log.info("collecting %d competitor pages…", len(sources["web"]))
    items += collect_web(sources["web"])

    for it in items:
        it["tags"] = _tag_and_classify(it, tagger, classifier)

    new = dbm.upsert_items(conn, items)
    log.info("collected %d items (%d new)", len(items), new)


def cmd_analyze(conn, args) -> None:
    """Re-tag and re-classify every stored item against the current taxonomy."""
    taxonomy = load_taxonomy(args.config)
    tagger = Tagger(taxonomy)
    classifier = NewsClassifier(taxonomy)
    count = 0
    for it in dbm.all_items(conn):
        dbm.update_tags(conn, it["id"], _tag_and_classify(it, tagger, classifier))
        count += 1
    conn.commit()
    log.info("re-tagged %d items", count)


def cmd_report(conn, args) -> None:
    prev_start, cur_start, now_iso = period_bounds(args.days)
    current = dbm.items_since(conn, cur_start)
    previous = dbm.items_between(conn, prev_start, cur_start)
    everything = dbm.all_items(conn)
    log.info("report window: %d current items, %d prior-period items",
             len(current), len(previous))

    insights = None
    if not args.no_llm:
        if llm.credentials_available():
            # Refine product/business labels on the reporting window (keyword
            # classification is the persisted baseline; this sharpens the
            # ambiguous cases in-memory for the report).
            refine_pool = current + previous
            overrides = llm.classify_news_types(refine_pool)
            if overrides:
                applied = 0
                for it in refine_pool:
                    label_key = overrides.get(it["id"])
                    if label_key:
                        it["tags"]["news_type"] = [LABELS[label_key]]
                        applied += 1
                log.info("Claude refined %d product/business labels", applied)

            log.info("generating Claude insight brief…")
            insights = llm.generate_insights(notable_items(current, limit=50))
            if insights is None:
                log.warning("insight brief unavailable; continuing without it")
        else:
            log.info("no Anthropic credentials found; skipping Claude "
                     "classification + insight brief (set ANTHROPIC_API_KEY)")

    prod = news_items(current, "Product")
    log.info("classified: %d product-level, %d business-level news items "
             "this period",
             len(prod), len(news_items(current, "Business")))

    args.out.mkdir(parents=True, exist_ok=True)
    digest = render_digest(current, previous, args.days, insights)
    dashboard = render_dashboard(current, previous, everything, args.days, insights)

    date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (args.out / f"digest-{date_tag}.md").write_text(digest, encoding="utf-8")
    (args.out / "digest-latest.md").write_text(digest, encoding="utf-8")
    (args.out / "dashboard.html").write_text(dashboard, encoding="utf-8")
    log.info("wrote %s, digest-%s.md, digest-latest.md",
             args.out / "dashboard.html", date_tag)


if __name__ == "__main__":
    sys.exit(main())
