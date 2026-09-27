"""Import user-provided X history exports without using the X API."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime
from typing import Any

FIELD_ALIASES = {
    "external_id": ["id", "post_id", "tweet_id", "tweetId", "id_str"],
    "text": ["text", "full_text", "content", "tweet", "post"],
    "published_at": ["published_at", "created_at", "createdAt", "date", "timestamp"],
    "impressions": ["impressions", "views", "view_count", "impression_count"],
    "likes": ["likes", "like_count", "favorite_count", "favorites"],
    "replies": ["replies", "reply_count"],
    "reposts": ["reposts", "retweets", "retweet_count"],
    "bookmarks": ["bookmarks", "bookmark_count"],
    "quotes": ["quotes", "quote_count"],
    "profile_visits": ["profile_visits", "profile_visits_count"],
}


def _pick(row: dict[str, Any], names: list[str]) -> Any:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        value = row.get(name)
        if value is None:
            value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def normalize_post(row: dict[str, Any], index: int = 0) -> dict[str, Any]:
    external_id = _pick(row, FIELD_ALIASES["external_id"])
    text = _pick(row, FIELD_ALIASES["text"]) or ""
    published_at = _datetime(_pick(row, FIELD_ALIASES["published_at"]))
    identity = str(external_id or f"{published_at or ''}|{text}|{index}")
    post_id = "xpost-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    post = {
        "id": post_id,
        "external_id": str(external_id) if external_id is not None else None,
        "text": str(text),
        "published_at": published_at,
        "source": "x_export",
    }
    for metric in ("impressions", "likes", "replies", "reposts",
                   "bookmarks", "quotes", "profile_visits"):
        value = _pick(row, FIELD_ALIASES[metric])
        if value is not None:
            post[metric] = _int(value)
    return post


def parse_json(payload: str | bytes | dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    data = payload if isinstance(payload, (dict, list)) else json.loads(payload)
    if isinstance(data, dict):
        for key in ("posts", "tweets", "data", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of posts or an object containing posts/tweets/data/items")
    return [normalize_post(item, i) for i, item in enumerate(data) if isinstance(item, dict)]


def parse_csv(payload: str | bytes) -> list[dict[str, Any]]:
    text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
    rows = csv.DictReader(io.StringIO(text))
    if not rows.fieldnames:
        raise ValueError("CSV must contain a header row")
    return [normalize_post(row, i) for i, row in enumerate(rows)]


def parse_payload(payload: str | bytes, fmt: str) -> list[dict[str, Any]]:
    fmt = fmt.lower().strip()
    if fmt == "json":
        posts = parse_json(payload)
    elif fmt == "csv":
        posts = parse_csv(payload)
    else:
        raise ValueError("format must be csv or json")
    posts = [p for p in posts if p["text"].strip()]
    if not posts:
        raise ValueError("no posts with non-empty text were found")
    return posts
