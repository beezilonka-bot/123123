"""Lightweight event clustering and trend scoring for the radar MVP.

No vector database or external ML service is required. The first pass uses
normalized title tokens and explainable heuristics so it can run cheaply on
the deployed service and be replaced later.
"""
from __future__ import annotations

import re
import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?")
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "as",
    "at", "by", "with", "from", "after", "before", "over", "into", "is",
    "are", "was", "were", "this", "that", "says", "say", "new",
}


def title_tokens(title: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(title or "")
        if token.lower() not in STOPWORDS and len(token) > 1
    }


def similarity(left: str, right: str) -> float:
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_items(items: list[dict[str, Any]], threshold: float = 0.45) -> list[dict[str, Any]]:
    """Group near-duplicate/same-event headlines using deterministic similarity."""
    clusters: list[dict[str, Any]] = []
    for item in items:
        best = None
        best_score = 0.0
        for cluster in clusters:
            score = max(similarity(item.get("title", ""), member.get("title", ""))
                        for member in cluster["items"])
            if score >= threshold and score > best_score:
                best, best_score = cluster, score
        if best is None:
            clusters.append({"items": [item]})
        else:
            best["items"].append(item)

    events: list[dict[str, Any]] = []
    for cluster in clusters:
        members = cluster["items"]
        dated = [m for m in members if m.get("published_at")]
        dated.sort(key=lambda m: m["published_at"])
        representative = max(members, key=lambda m: len(m.get("summary") or ""))
        identity_item = dated[0] if dated else sorted(members, key=lambda m: m.get("id", ""))[0]
        identity = identity_item.get("id") or identity_item.get("canonical_url") or representative.get("title", "")
        cluster_key = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()[:16]
        sources = {m.get("source_id") for m in members if m.get("source_id")}
        events.append({
            "id": f"event-{cluster_key}",
            "representative_item_id": representative.get("id"),
            "title": representative.get("title"),
            "summary": representative.get("summary"),
            "first_seen_at": dated[0]["published_at"] if dated else None,
            "latest_seen_at": dated[-1]["published_at"] if dated else None,
            "item_count": len(members),
            "source_count": len(sources),
            "items": members,
            "cluster_key": cluster_key,
        })
    return events


def _age_hours(value: str | None, now: datetime) -> float:
    if not value:
        return 24.0
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt.astimezone(timezone.utc)).total_seconds() / 3600)
    except ValueError:
        return 24.0


def score_events(events: list[dict[str, Any]], topics: list[str] | None = None,
                 now: datetime | None = None,
                 history: dict[str, dict[str, float]] | None = None) -> list[dict[str, Any]]:
    """Return explainable 0-100 trend scores, sorted descending."""
    now = now or datetime.now(timezone.utc)
    topic_tokens = set().union(*(title_tokens(t) for t in (topics or [])))
    scored = []
    for event in events:
        age = _age_hours(event.get("latest_seen_at"), now)
        freshness = max(0.0, min(1.0, 1.0 - age / 48.0))
        source_signal = min(1.0, event.get("source_count", 0) / 4.0)
        volume_signal = min(1.0, event.get("item_count", 0) / 5.0)
        hist = (history or {}).get(event.get("cluster_key", ""), {})
        previous = hist.get("previous_item_count", 0.0)
        elapsed = max(hist.get("elapsed_hours", 1.0), 0.25)
        velocity = max(0.0, (event.get("item_count", 0) - previous) / elapsed)
        velocity_signal = min(1.0, velocity / 3.0)
        title_signal = title_tokens(event.get("title", ""))
        relevance = (
            len(title_signal & topic_tokens) / len(topic_tokens)
            if topic_tokens else 0.0
        )
        novelty = 1.0 if age <= 6 else max(0.0, 1.0 - age / 48.0)
        total = 100 * (
            0.35 * freshness +
            0.25 * source_signal +
            0.10 * volume_signal +
            0.05 * velocity_signal +
            0.15 * novelty +
            0.10 * relevance
        )
        scored.append({
            **event,
            "trend_signal": {
                "freshness": round(freshness, 4),
                "velocity": round(velocity_signal, 4),
                "source_count": event.get("source_count", 0),
                "item_count": event.get("item_count", 0),
                "novelty": round(novelty, 4),
                "relevance": round(relevance, 4),
                "total_score": round(total, 2),
                "calculated_at": now.isoformat(),
            },
        })
    return sorted(scored, key=lambda e: e["trend_signal"]["total_score"], reverse=True)
