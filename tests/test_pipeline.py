"""End-to-end pipeline test on fixture data (no network).

Run with: python -m pytest tests/  (or plain `python tests/test_pipeline.py`)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voc import db as dbm  # noqa: E402
from voc.analysis import (  # noqa: E402
    news_items,
    news_type_counts,
    period_bounds,
    tag_counts,
    weekly_volume,
)
from voc.classify import LABELS, NewsClassifier  # noqa: E402
from voc.config import load_taxonomy  # noqa: E402
from voc.report import render_dashboard, render_digest  # noqa: E402
from voc.tagging import Tagger  # noqa: E402


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(
        timespec="seconds"
    )


def make_fixture_items() -> list[dict]:
    return [
        {
            "source": "r/accesscontrol",
            "source_type": "reddit",
            "title": "HES 1006 electric strike buzzing but not releasing — wiring issue?",
            "url": "https://www.reddit.com/r/accesscontrol/1",
            "author": "installer42",
            "published": _iso(1),
            "body": "Installed a HES 1006 on an aluminum storefront, 12VDC power "
                    "supply, it buzzes but the keeper won't release. Voltage drop?",
            "score": 42,
            "num_comments": 17,
        },
        {
            "source": "r/accesscontrol",
            "source_type": "reddit",
            "title": "Securitron M680E vs generic maglock — worth the price?",
            "url": "https://www.reddit.com/r/accesscontrol/2",
            "author": "lowvoltguy",
            "published": _iso(2),
            "body": "Customer wants delayed egress. Is the Securitron holding force "
                    "rating worth it over a cheap magnetic lock? Also looking at "
                    "Seco-Larm as an alternative to keep cost down.",
            "score": 15,
            "num_comments": 9,
        },
        {
            "source": "SDM Magazine",
            "source_type": "rss",
            "title": "Von Duprin launches new exit device with latch retraction",
            "url": "https://example.com/vonduprin-launch",
            "author": None,
            "published": _iso(3),
            "body": "Allegion brand Von Duprin announced a panic hardware line with "
                    "quiet electric latch retraction and PoE power option.",
            "score": None,
            "num_comments": None,
        },
        {
            "source": "Locksmith Ledger",
            "source_type": "rss",
            "title": "Choosing fail safe vs fail secure electric strikes for fire-rated openings",
            "url": "https://example.com/failsafe",
            "author": None,
            "published": _iso(5),
            "body": "NFPA and UL 10C considerations when speccing an electric strike "
                    "on a fire rated door. Free egress must be maintained.",
            "score": None,
            "num_comments": None,
        },
        {
            "source": "Camden Door Controls news",
            "source_type": "web",
            "title": "Camden Door Controls introduces new request to exit sensor line",
            "url": "https://example.com/camden-rex",
            "author": None,
            "published": None,
            "collected_at": _iso(0.5),
            "body": None,
            "score": None,
            "num_comments": None,
        },
        # prior-period item for delta math
        {
            "source": "r/accesscontrol",
            "source_type": "reddit",
            "title": "Adams Rite 7400 deadlatch replacement on storefront door",
            "url": "https://www.reddit.com/r/accesscontrol/3",
            "author": "glazier9",
            "published": _iso(10),
            "body": "Replacing an Adams Rite deadlatch, need a compatible electric strike.",
            "score": 8,
            "num_comments": 4,
        },
    ]


def test_pipeline(tmp_path=None):
    tmp_path = tmp_path or Path("/tmp/voc-test")
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"
    if db_path.exists():
        db_path.unlink()

    taxonomy = load_taxonomy()
    tagger = Tagger(taxonomy)
    classifier = NewsClassifier(taxonomy)
    items = make_fixture_items()
    for it in items:
        it["tags"] = tagger.tag(it["title"], it.get("body"))
        result = classifier.classify(
            it["title"], it.get("body"), it["tags"], it["source_type"]
        )
        if result is not None:
            it["tags"]["news_type"] = [LABELS[result[0]]]

    # --- tagging assertions
    by_url = {it["url"]: it for it in items}
    hes = by_url["https://www.reddit.com/r/accesscontrol/1"]["tags"]
    assert "HES" in hes.get("own_brands", []), hes
    assert "Electric strikes" in hes.get("categories", []), hes
    assert "Installation & troubleshooting" in hes.get("themes", []), hes

    # Von Duprin is consolidated under the Allegion umbrella competitor, and
    # an item mentioning both "Von Duprin" and "Allegion" counts once.
    vd = by_url["https://example.com/vonduprin-launch"]["tags"]
    assert vd.get("competitors") == ["Allegion (Schlage / Von Duprin / LCN)"], vd
    assert "Exit devices & panic hardware" in vd.get("categories", []), vd

    sec = by_url["https://www.reddit.com/r/accesscontrol/2"]["tags"]
    assert "Securitron" in sec.get("own_brands", []), sec
    assert "Seco-Larm" in sec.get("competitors", []), sec

    # word-boundary sanity: "rci" must not fire on unrelated words
    assert "RCI" not in tagger.tag("Commercial door hardware overview").get(
        "competitors", []
    )

    # newly added EMS own brands are recognized
    assert "Control iD" in tagger.tag(
        "Control iD releases new facial recognition reader"
    ).get("own_brands", [])
    assert "LifeSafety Power" in tagger.tag(
        "LifeSafety Power announces new FlexPower supply", None
    ).get("own_brands", [])

    # --- product vs business classification
    vd_launch = by_url["https://example.com/vonduprin-launch"]["tags"]
    assert vd_launch.get("news_type") == ["Product"], vd_launch  # "launches"
    # a Reddit discussion is not news → no news_type label
    assert "news_type" not in hes

    # direct classifier checks on unambiguous headlines
    assert classifier.classify(
        "dormakaba appoints new CEO effective next quarter", None, {}, "rss"
    )[0] == "business"
    assert classifier.classify(
        "SDC unveils new fail-safe electric strike with PoE", None, {}, "rss"
    )[0] == "product"
    assert classifier.classify(
        "Minuteman Security acquires Performance Link Technologies", None, {}, "rss"
    )[0] == "business"
    # Reddit source is never classified as news
    assert classifier.classify("anything", None, {}, "reddit") is None

    # A story ABOUT a product is product-level even without launch language,
    # signalled by a tagged product category.
    cat_only = {"categories": ["Exit devices & panic hardware"]}
    assert classifier.classify(
        "Why Allegion's Von Duprin 98/99 exit device dominates busy doors",
        None, cat_only, "rss",
    )[0] == "product"
    # ...but a business event about a product-maker is still business.
    assert classifier.classify(
        "Firm that makes exit devices acquired by private equity",
        None, cat_only, "rss",
    )[0] == "business"

    # --- storage round-trip + dedupe
    conn = dbm.connect(db_path)
    assert dbm.upsert_items(conn, items) == len(items)
    assert dbm.upsert_items(conn, items) == 0  # idempotent

    prev_start, cur_start, _ = period_bounds(7)
    current = dbm.items_since(conn, cur_start)
    previous = dbm.items_between(conn, prev_start, cur_start)
    assert len(current) == 5, [i["title"] for i in current]
    assert len(previous) == 1

    cats = tag_counts(current, "categories")
    assert cats["Electric strikes"] >= 2

    vol = weekly_volume(dbm.all_items(conn))
    assert len(vol) == 12 and sum(v for _, v in vol) == len(items)

    # classification counts + filtering
    nt = news_type_counts(current)
    assert nt.get("Product", 0) >= 1
    prod = news_items(current, "Product")
    assert any("Von Duprin" in it["title"] for it in prod)

    # --- reports render and contain the expected content
    digest = render_digest(current, previous, 7)
    assert "Electric strikes" in digest and "Von Duprin" in digest
    assert "Product-level news" in digest and "Business-level news" in digest

    dash = render_dashboard(current, previous, dbm.all_items(conn), 7,
                            insights_md="## Key takeaways\n- **Test** insight [#1]")
    assert "<!DOCTYPE html>" in dash
    assert "Brand share of voice" in dash
    assert "Securitron" in dash
    assert "<strong>Test</strong>" in dash
    assert "Product-level news" in dash and "Business-level news" in dash

    # product-news category filter: a chip row plus rows carrying data-cat
    assert 'class="cat-filter"' in dash
    assert 'data-category="__all__"' in dash
    assert "data-cat=" in dash

    # drill-down: clickable bars + a hidden panel per bar, and every row's
    # data-target must resolve to a panel id on the page.
    assert 'class="barrow drill-row"' in dash
    import re as _re
    targets = _re.findall(r'data-target="([^"]+)"', dash)
    assert targets, "no drillable bars rendered"
    for pid in targets:
        assert f'id="{pid}"' in dash, f"missing panel for {pid}"
    # a category drill panel should contain a contributing story link
    assert 'class="drill-panel"' in dash and 'class="drill-item"' in dash

    out = tmp_path / "dashboard.html"
    out.write_text(dash, encoding="utf-8")
    conn.close()
    print(f"OK — dashboard written to {out}")


if __name__ == "__main__":
    test_pipeline()
