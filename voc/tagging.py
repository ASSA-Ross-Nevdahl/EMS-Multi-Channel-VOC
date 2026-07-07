"""Keyword tagging of items against the taxonomy.

Matching is case-insensitive and anchored on word boundaries, so "rci" does
not match "commercial" and "hes" does not match "these". Multi-word phrases
match across whitespace.
"""

from __future__ import annotations

import re


class Tagger:
    def __init__(self, taxonomy: dict):
        self._matchers: dict[str, list[tuple[str, re.Pattern]]] = {
            "categories": _compile_group(taxonomy.get("categories", {})),
            "themes": _compile_group(taxonomy.get("themes", {})),
        }
        brands = taxonomy.get("brands", {})
        for group_key, tag_key in (
            ("own", "own_brands"),
            ("assa_abloy_other", "assa_abloy_other"),
            ("competitors", "competitors"),
        ):
            self._matchers[tag_key] = _compile_brand_group(brands.get(group_key, {}))

    def tag(self, title: str, body: str | None = None) -> dict:
        text = f"{title}\n{body or ''}"
        tags: dict[str, list[str]] = {}
        for tag_key, matchers in self._matchers.items():
            hits = [name for name, pattern in matchers if pattern.search(text)]
            if hits:
                tags[tag_key] = hits
        return tags


def _phrase_pattern(keywords: list[str]) -> re.Pattern:
    parts = []
    for kw in keywords:
        escaped = re.escape(kw.strip().lower()).replace(r"\ ", r"\s+")
        parts.append(rf"(?<![\w-]){escaped}(?![\w-])" if kw[-1].isalnum()
                     else rf"(?<![\w-]){escaped}")
    return re.compile("|".join(parts), re.IGNORECASE)


def _compile_group(group: dict) -> list[tuple[str, re.Pattern]]:
    """Categories/themes: {key: {label, keywords}} -> [(label, pattern)]."""
    out = []
    for entry in group.values():
        label = entry.get("label") or "?"
        keywords = entry.get("keywords") or []
        if keywords:
            out.append((label, _phrase_pattern(keywords)))
    return out


def _compile_brand_group(group: dict) -> list[tuple[str, re.Pattern]]:
    """Brands: {Brand Name: {keywords}} -> [(Brand Name, pattern)]."""
    out = []
    for name, entry in group.items():
        keywords = entry.get("keywords") or []
        if keywords:
            out.append((name, _phrase_pattern(keywords)))
    return out
