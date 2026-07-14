"""Product-vs-business news classification.

Trade-press and competitor-news items split into two buckets that matter to
a product manager:

  - **Product** — the story is about a product: a launch or new feature, but
    also any coverage of a specific product or product category (a review,
    an explainer, a spec/firmware/certification/recall note, an integration).
  - **Business** — corporate/market activity: M&A, executive changes,
    financials, distribution deals, facility expansion, awards.

Decision rule (in order):

  1. A genuine **business event** (an M&A / leadership / earnings keyword)
     is decisive — even when a product is mentioned — unless product/launch
     language clearly outweighs it. ("Company that makes exit devices is
     acquired" is business, not product.)
  2. Otherwise, anything **about a product** — product/launch language OR a
     tagged product category (electric strike, maglock, exit device, …) —
     is product-level. A story does not need to announce a launch; being
     about the product is enough.
  3. Everything else is "other".

The category signal comes from the same keyword taxonomy as the rest of the
tagging, so it's transparent and editable. The optional Claude pass (see
`llm.py`) can still refine genuinely ambiguous cases when credentials exist.

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
        has_category = bool((tags or {}).get("categories"))

        # 1. A business event is decisive unless launch language outweighs it.
        if b > 0 and b >= p:
            return "business", f"business signal dominates ({b} business vs {p} product)"
        # 2. Anything about a specific product — launch language OR a tagged
        #    product category — is product-level.
        if p > 0:
            return "product", f"product/launch language ({p} signals)"
        if has_category:
            return "product", "story is about a tagged product category"
        # 3. No product or business signal at all.
        return "other", "no product or business signal"


def news_type_of(item: dict) -> str | None:
    """The stored display label ('Product'/'Business'/'Other'), or None."""
    values = item.get("tags", {}).get("news_type")
    return values[0] if values else None
