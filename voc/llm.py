"""Optional LLM insight brief via the Claude API.

Runs only when an Anthropic credential is available (ANTHROPIC_API_KEY or an
`ant auth login` profile). The rest of the pipeline works without it.
"""

from __future__ import annotations

import json
import logging
import os

log = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are a market analyst supporting product managers in the Electromechanical
Solutions Group at ASSA ABLOY (brands: HES electric strikes, Securitron
maglocks and power, Alarm Controls switches/PSUs, Adams Rite aluminum-door
hardware). You will receive a batch of recent public items — trade-press
articles, Reddit discussions from installers and integrators, and competitor
news headlines — about commercial access control and door hardware.

A core job is separating **product-level** developments (roadmap-relevant:
launches, new features, spec/firmware changes, certifications, recalls,
integrations) from **business-level** activity (M&A, executive changes,
financials, distribution deals, facility expansion, awards). Product
managers care most about the former; keep the two clearly separated.

Write a concise insight brief in Markdown with exactly these sections:

## Product-level developments
The roadmap-relevant news: new/updated products, features, specs,
certifications, recalls, integrations — competitors' and the field's.
Lead with anything that affects electric strikes, maglocks, exit devices,
power supplies, or aluminum-door hardware. If nothing meaningful, say so
in one line.

## Business-level activity
M&A, leadership changes, financials, distribution/channel moves, expansion,
awards — only what a PM should be aware of for competitive context. Keep it
brief; this is background, not the headline.

## Voice of the field
Pain points, praise, and recurring questions from installers/integrators
(mostly the Reddit items). Quote or closely paraphrase where useful, and
name the brand/product when mentioned.

## Suggested follow-ups
2-4 concrete actions for the PM team (e.g., topics to investigate, items
tech support should prepare for, competitive gaps).

Ground every claim in the provided items; cite items inline as [#N] using
the item numbers given. Do not invent items or statistics.
"""

CLASSIFY_SYSTEM = """\
You classify commercial access-control / door-hardware news headlines for a
product-management team. For each item, decide whether it is primarily:

- "product": a product-level development — a new or updated product, feature,
  spec, firmware, certification, recall, or integration. Roadmap-relevant.
- "business": a business-level development — M&A, executive/leadership
  change, financial results, funding, distribution/channel deal, facility
  expansion, award, rebrand, or event.
- "other": neither clearly applies (general commentary, how-to, opinion).

Judge by what the item is fundamentally ABOUT, not by whether a product is
merely mentioned (a company being acquired is "business" even if it makes
strikes). Return your answer using the provided structured format only.
"""

CLASSIFY_MODEL = "claude-opus-4-8"
MAX_CLASSIFY = 150


def credentials_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # `ant auth login` profile on disk
    cfg = os.path.expanduser("~/.config/anthropic")
    return os.path.isdir(cfg) and bool(os.listdir(cfg))


def generate_insights(items: list[dict], max_items: int = 50) -> str | None:
    """Return a Markdown insight brief, or None if the LLM is unavailable."""
    if not items:
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed; skipping LLM insights")
        return None

    corpus = _format_items(items[:max_items])
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": corpus}],
        )
    except anthropic.APIError as exc:
        log.warning("Claude API call failed: %s", exc)
        return None
    if response.stop_reason == "refusal":
        log.warning("Claude declined the request (stop_reason=refusal)")
        return None
    return "".join(b.text for b in response.content if b.type == "text").strip()


def classify_news_types(items: list[dict], max_items: int = MAX_CLASSIFY) -> dict:
    """Classify news items as product/business/other in one batched call.

    Returns {item_id: label_key} for items the model labeled; an empty dict
    if the LLM is unavailable or the call fails. Only news-source items
    (those already carrying a keyword news_type label) are sent.
    """
    news = [it for it in items if it.get("tags", {}).get("news_type")][:max_items]
    if not news:
        return {}
    try:
        import anthropic
    except ImportError:
        return {}

    numbered = "\n".join(
        f"{i}. ({it['source']}) {it['title']}" for i, it in enumerate(news, 1)
    )
    schema = {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "n": {"type": "integer"},
                        "label": {"type": "string",
                                  "enum": ["product", "business", "other"]},
                    },
                    "required": ["n", "label"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["labels"],
        "additionalProperties": False,
    }
    client = anthropic.Anthropic()
    try:
        resp = client.messages.create(
            model=CLASSIFY_MODEL,
            max_tokens=8000,
            system=CLASSIFY_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content":
                       f"Classify each item:\n\n{numbered}"}],
        )
    except anthropic.APIError as exc:
        log.warning("Claude classification failed: %s", exc)
        return {}
    if resp.stop_reason == "refusal":
        log.warning("Claude declined the classification request")
        return {}

    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        log.warning("could not parse Claude classification output")
        return {}

    out: dict = {}
    for entry in parsed.get("labels", []):
        idx, label = entry.get("n"), entry.get("label")
        if isinstance(idx, int) and 1 <= idx <= len(news) and label in (
            "product", "business", "other"
        ):
            out[news[idx - 1]["id"]] = label
    return out


def _format_items(items: list[dict]) -> str:
    lines = ["Recent items (most engaging/recent first):", ""]
    for i, it in enumerate(items, 1):
        tags = it.get("tags", {})
        tag_bits = ", ".join(
            f"{k}: {', '.join(v)}" for k, v in sorted(tags.items()) if v
        )
        engagement = ""
        if it.get("score") is not None:
            engagement = f" | {it['score']} points, {it.get('num_comments') or 0} comments"
        lines.append(
            f"[#{i}] ({it['source']}{engagement}) {it['title']}"
        )
        if tag_bits:
            lines.append(f"     tags: {tag_bits}")
        body = (it.get("body") or "").strip()
        if body:
            lines.append(f"     excerpt: {body[:600]}")
        lines.append(f"     url: {it['url']}")
        lines.append("")
    return "\n".join(lines)
