"""Product-vs-business news classification.

Trade-press and competitor-news items split into two buckets that matter to
a product manager:

  - **Product** — roadmap-relevant: launches, new features, spec/firmware
    changes, certifications, recalls, integrations.
  - **Business** — corporate/market activity: M&A, executive changes,
    financials, distribution deals, facility expansion, awards.

The classifier scores an item's text against the two keyword lists in
`taxonomy.yaml` (`news_type:`) and assigns the higher-scoring bucket, or
"other" when there is no clear signal or the two tie. It is intentionally
transparent and editable; the optional Claude pass (see `llm.py`) refines
the ambiguous cases when credentials are available.

Reddit discussion is not "news" in this sense and is left unclassified.
"""

from __future__ import annotations

from .tagging import phrase_pattern

# key -> display label used in reports and stored in tags["news_type"]
LABELS = {"product": "Product", "business": "Business", "other": "Other"}

# source types that carry news (Reddit is installer discussion, not news)
NEWS_SOURCE_TYPES = {"rss", "web"}


class NewsClassifier:
    def __init__(self, taxonomy: dict):
        nt = taxonomy.get("news_type", {}) or {}
        self._product = phrase_pattern(
            (nt.get("product", {}) or {}).get("keywords") or ["\0"]
        )
        self._business = phrase_pattern(
            (nt.get("business", {}) or {}).get("keywords") or ["\0"]
        )

    def classify(
        self, title: str, body: str | None, tags: dict | None, source_type: str
    ) -> tuple[str, str] | None:
        """Return (label_key, reason), or None for non-news sources."""
        if source_type not in NEWS_SOURCE_TYPES:
            return None
        text = f"{title}\n{body or ''}"
        p = len(self._product.findall(text))
        b = len(self._business.findall(text))
        if p == 0 and b == 0:
            return "other", "no product or business signals"
        if p > b:
            return "product", f"{p} product vs {b} business signals"
        if b > p:
            return "business", f"{b} business vs {p} product signals"
        # tie with signals on both sides: lean product only if a concrete
        # product category was also detected, else leave ambiguous.
        if tags and tags.get("categories"):
            return "product", "tie broken by product-category mention"
        return "other", "mixed product/business signals"


def news_type_of(item: dict) -> str | None:
    """The stored display label ('Product'/'Business'/'Other'), or None."""
    values = item.get("tags", {}).get("news_type")
    return values[0] if values else None
