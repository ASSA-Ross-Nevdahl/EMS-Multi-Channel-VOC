"""Source collectors. Each collector returns a list of normalized item dicts:

{
    "source": str,        # display name of the source
    "source_type": str,   # rss | reddit | web
    "title": str,
    "url": str,
    "author": str | None,
    "published": str | None,   # ISO 8601 UTC
    "body": str | None,        # plain-text summary / selftext excerpt
    "score": int | None,       # reddit upvotes
    "num_comments": int | None,
}
"""

from .rss import collect_rss
from .reddit import collect_reddit
from .web import collect_web

__all__ = ["collect_rss", "collect_reddit", "collect_web"]
