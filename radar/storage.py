"""PostgreSQL persistence for the radar loop."""
from __future__ import annotations

import os
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'rss', enabled BOOLEAN NOT NULL DEFAULT TRUE,
    credibility DOUBLE PRECISION, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
    url TEXT NOT NULL, canonical_url TEXT NOT NULL, title TEXT NOT NULL,
    summary TEXT, content TEXT, author TEXT, published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL, language TEXT, raw_hash TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_canonical_url ON items(canonical_url);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, representative_item_id TEXT, title TEXT NOT NULL,
    summary TEXT, first_seen_at TIMESTAMPTZ, latest_seen_at TIMESTAMPTZ,
    item_count INTEGER NOT NULL DEFAULT 0, source_count INTEGER NOT NULL DEFAULT 0,
    cluster_key TEXT, status TEXT NOT NULL DEFAULT 'active',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS trend_signals (
    id BIGSERIAL PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
    freshness DOUBLE PRECISION NOT NULL, velocity DOUBLE PRECISION NOT NULL,
    source_count DOUBLE PRECISION NOT NULL, item_count DOUBLE PRECISION NOT NULL,
    novelty DOUBLE PRECISION NOT NULL, relevance DOUBLE PRECISION NOT NULL,
    total_score DOUBLE PRECISION NOT NULL, calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trend_event_time ON trend_signals(event_id, calculated_at DESC);
CREATE TABLE IF NOT EXISTS content_opportunities (
    id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
    title TEXT NOT NULL, why_now TEXT, audience TEXT, angle TEXT,
    suggested_format TEXT, priority DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_opportunities_created ON content_opportunities(created_at DESC);
"""

def database_url() -> str | None:
    return os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

def enabled() -> bool:
    return bool(database_url())

def _connect():
    import psycopg
    return psycopg.connect(database_url())

def init_db() -> None:
    if not enabled():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)

def persist_run(sources: list[dict[str, Any]], items: list[dict[str, Any]],
                events: list[dict[str, Any]]) -> dict[str, int]:
    if not enabled():
        return {"persisted_sources": 0, "persisted_items": 0, "persisted_events": 0}
    init_db()
    with _connect() as conn:
        with conn.cursor() as cur:
            for source in sources:
                cur.execute(
                    """INSERT INTO sources(id,name,url,type) VALUES(%s,%s,%s,%s)
                    ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,url=EXCLUDED.url,
                    type=EXCLUDED.type,updated_at=NOW()""",
                    (source["id"],source["name"],source["url"],source.get("type","rss")))
            for item in items:
                cur.execute(
                    """INSERT INTO items(id,source_id,url,canonical_url,title,summary,content,author,
                    published_at,fetched_at,language,raw_hash)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(id) DO UPDATE SET fetched_at=EXCLUDED.fetched_at,summary=EXCLUDED.summary""",
                    (item["id"],item["source_id"],item["url"],item["canonical_url"],item["title"],
                     item.get("summary"),item.get("content"),item.get("author"),item.get("published_at"),
                     item["fetched_at"],item.get("language"),item["raw_hash"]))
            for event in events:
                cur.execute(
                    """INSERT INTO events(id,representative_item_id,title,summary,first_seen_at,
                    latest_seen_at,item_count,source_count,cluster_key,status)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(id) DO UPDATE SET representative_item_id=EXCLUDED.representative_item_id,
                    title=EXCLUDED.title,summary=EXCLUDED.summary,latest_seen_at=EXCLUDED.latest_seen_at,
                    item_count=EXCLUDED.item_count,source_count=EXCLUDED.source_count,
                    cluster_key=EXCLUDED.cluster_key,status=EXCLUDED.status,updated_at=NOW()""",
                    (event["id"],event.get("representative_item_id"),event["title"],event.get("summary"),
                     event.get("first_seen_at"),event.get("latest_seen_at"),event["item_count"],
                     event["source_count"],event.get("cluster_key"),event.get("status","active")))
                signal=event.get("trend_signal")
                if signal:
                    cur.execute(
                        """INSERT INTO trend_signals(event_id,freshness,velocity,source_count,item_count,
                        novelty,relevance,total_score) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (event["id"],signal["freshness"],signal["velocity"],signal["source_count"],
                         signal["item_count"],signal["novelty"],signal["relevance"],signal["total_score"]))
        conn.commit()
    return {"persisted_sources":len(sources),"persisted_items":len(items),"persisted_events":len(events)}

def recent_events(limit: int = 30) -> list[dict[str, Any]]:
    if not enabled():
        return []
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT e.id,e.title,e.summary,e.item_count,e.source_count,
                       e.first_seen_at,e.latest_seen_at,t.total_score,t.velocity
                       FROM events e LEFT JOIN LATERAL
                       (SELECT * FROM trend_signals WHERE event_id=e.id
                        ORDER BY calculated_at DESC LIMIT 1) t ON TRUE
                       WHERE e.status='active' ORDER BY COALESCE(t.total_score,0) DESC LIMIT %s""",(limit,))
        cols=[d.name for d in cur.description]
        return [dict(zip(cols,row)) for row in cur.fetchall()]
