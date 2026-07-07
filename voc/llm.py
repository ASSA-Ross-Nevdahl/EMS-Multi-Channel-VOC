"""Optional LLM insight brief via the Claude API.

Runs only when an Anthropic credential is available (ANTHROPIC_API_KEY or an
`ant auth login` profile). The rest of the pipeline works without it.
"""

from __future__ import annotations

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

Write a concise insight brief in Markdown with exactly these sections:

## Key takeaways
3-5 bullets. What a product manager should know this period.

## Competitor activity
What competitors (Von Duprin/Allegion, dormakaba, SDC, Camden, Trine,
Seco-Larm, Detex, etc.) announced or what the field is saying about them.
If nothing meaningful, say so in one line.

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
