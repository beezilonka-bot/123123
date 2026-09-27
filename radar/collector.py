"""Minimal RSS/Atom collector for 123123.

The collector is intentionally small: fetch one feed, normalize entries,
canonicalize URLs, and emit deterministic Item dictionaries.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}


def canonicalize_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    if not parts.scheme or not parts.netloc:
        return (url or "").strip()
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def raw_hash(title: str, canonical_url: str) -> str:
    value = f"{title.strip()}\n{canonical_url}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _iso(value: Any) -> str | None:
    if not value:
        return None
    try:
        dt = datetime(*value[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    except (TypeError, ValueError):
        return None


def collect_feed(feed_url: str, source_id: str, source_name: str) -> list[dict[str, Any]]:
    parsed = feedparser.parse(feed_url)
    fetched_at = datetime.now(timezone.utc).isoformat()
    items: list[dict[str, Any]] = []

    for entry in parsed.entries:
        url = str(entry.get("link", "")).strip()
        title = str(entry.get("title", "")).strip()
        canonical_url = canonicalize_url(url)
        items.append({
            "id": raw_hash(title, canonical_url),
            "source_id": source_id,
            "source_name": source_name,
            "url": url,
            "canonical_url": canonical_url,
            "title": title,
            "summary": str(entry.get("summary", "")).strip() or None,
            "content": None,
            "author": str(entry.get("author", "")).strip() or None,
            "published_at": _iso(entry.get("published_parsed")),
            "fetched_at": fetched_at,
            "language": None,
            "raw_hash": raw_hash(title, canonical_url),
        })
    return items
