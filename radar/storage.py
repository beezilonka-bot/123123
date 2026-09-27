"""PostgreSQL persistence for the radar loop."""
from __future__ import annotations

import json
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
CREATE TABLE IF NOT EXISTS event_analyses (
    id BIGSERIAL PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
    importance DOUBLE PRECISION NOT NULL, why_it_matters TEXT,
    who_cares TEXT, key_facts JSONB, uncertainty TEXT, tags JSONB,
    suggested_angles JSONB, model TEXT, analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_analysis_event_time ON event_analyses(event_id, analyzed_at DESC);
CREATE TABLE IF NOT EXISTS account_posts (
    id TEXT PRIMARY KEY, external_id TEXT UNIQUE, text TEXT NOT NULL,
    published_at TIMESTAMPTZ, impressions BIGINT DEFAULT 0, likes BIGINT DEFAULT 0,
    replies BIGINT DEFAULT 0, reposts BIGINT DEFAULT 0, bookmarks BIGINT DEFAULT 0,
    quotes BIGINT DEFAULT 0, profile_visits BIGINT DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'x', imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_account_posts_published ON account_posts(published_at DESC);
CREATE TABLE IF NOT EXISTS account_metrics (
    id BIGSERIAL PRIMARY KEY, post_id TEXT NOT NULL REFERENCES account_posts(id),
    metric_name TEXT NOT NULL, metric_value DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
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
                    ON CONFLICT(canonical_url) DO UPDATE SET fetched_at=EXCLUDED.fetched_at,
                    summary=EXCLUDED.summary,title=EXCLUDED.title,source_id=EXCLUDED.source_id""",
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

def persist_analysis(analysis: dict[str, Any]) -> None:
    if not enabled():
        return
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO event_analyses(event_id,importance,why_it_matters,who_cares,
            key_facts,uncertainty,tags,suggested_angles,model)
            VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s)""",
            (analysis["event_id"],analysis.get("importance",0),analysis.get("why_it_matters"),
             analysis.get("who_cares"),json.dumps(analysis.get("key_facts",[]),ensure_ascii=False),
             analysis.get("uncertainty"),json.dumps(analysis.get("tags",[]),ensure_ascii=False),
             json.dumps(analysis.get("suggested_angles",[]),ensure_ascii=False),analysis.get("model")))
        conn.commit()

def recent_analyses(limit: int = 10) -> dict[str, dict[str, Any]]:
    if not enabled():
        return {}
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT DISTINCT ON (event_id) event_id,importance,why_it_matters,
                       who_cares,key_facts,uncertainty,tags,suggested_angles,model,analyzed_at
                       FROM event_analyses ORDER BY event_id,analyzed_at DESC""")
        rows=cur.fetchall()
        rows=sorted(rows,key=lambda x: float(x[1] or 0),reverse=True)[:limit]
        cols=[d.name for d in cur.description]
        return {str(row[0]):dict(zip(cols,row)) for row in rows}

def velocity_history() -> dict[str, dict[str, float]]:
    if not enabled():
        return {}
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT cluster_key,item_count,latest_seen_at FROM events
                       WHERE cluster_key IS NOT NULL AND latest_seen_at IS NOT NULL
                       ORDER BY latest_seen_at""")
        rows=cur.fetchall()
    grouped: dict[str, list[tuple[float, float]]] = {}
    for key, count, latest in rows:
        ts = latest.timestamp() if hasattr(latest, "timestamp") else 0.0
        grouped.setdefault(key, []).append((ts, float(count or 0)))
    out = {}
    for key, values in grouped.items():
        if len(values) >= 2:
            first_ts, first_count = values[0]
            last_ts, last_count = values[-1]
            elapsed=max((last_ts-first_ts)/3600.0, 0.25)
            out[key]={"previous_item_count":first_count,"elapsed_hours":elapsed}
    return out


def record_opportunity(opportunity: dict[str, Any]) -> None:
    if not enabled():
        return
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO content_opportunities
        (id,event_id,title,why_now,audience,angle,suggested_format,priority,expires_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(id) DO UPDATE SET title=EXCLUDED.title,why_now=EXCLUDED.why_now,
        audience=EXCLUDED.audience,angle=EXCLUDED.angle,suggested_format=EXCLUDED.suggested_format,
        priority=EXCLUDED.priority""",
        (opportunity["id"],opportunity["event_id"],opportunity["title"],
         opportunity.get("why_now"),opportunity.get("audience"),opportunity.get("angle"),
         opportunity.get("suggested_format","single_post"),opportunity.get("priority",0),
         opportunity.get("expires_at")))
        conn.commit()


def persist_account_posts(posts: list[dict[str, Any]]) -> int:
    if not enabled():
        return 0
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        for post in posts:
            cur.execute("""INSERT INTO account_posts
            (id,external_id,text,published_at,impressions,likes,replies,reposts,bookmarks,quotes,profile_visits,source)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(id) DO UPDATE SET text=EXCLUDED.text,published_at=EXCLUDED.published_at,
            external_id=EXCLUDED.external_id,impressions=EXCLUDED.impressions,
            likes=EXCLUDED.likes,replies=EXCLUDED.replies,reposts=EXCLUDED.reposts,
            bookmarks=EXCLUDED.bookmarks,quotes=EXCLUDED.quotes,
            profile_visits=EXCLUDED.profile_visits,source=EXCLUDED.source""",
            (post["id"],post.get("external_id"),post["text"],post.get("published_at"),
             post.get("impressions"),post.get("likes"),post.get("replies"),
             post.get("reposts"),post.get("bookmarks"),post.get("quotes"),
             post.get("profile_visits"),post.get("source","x"))) 
    conn.commit()
    return len(posts)


def account_posts(limit: int = 100) -> list[dict[str, Any]]:
    if not enabled():
        return []
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,external_id,text,published_at,impressions,likes,replies,
                       reposts,bookmarks,quotes,profile_visits
                       FROM account_posts ORDER BY published_at DESC NULLS LAST LIMIT %s""",(limit,))
        cols=[d.name for d in cur.description]
        return [dict(zip(cols,row)) for row in cur.fetchall()]


from statistics import median


def summarize_account_performance(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize only metrics actually supplied by the account data."""
    if not posts:
        return {"post_count": 0, "medians": {}, "top_posts": []}
    def rates(post):
        imp = max(float(post.get("impressions") or 0), 0.0) or 1.0
        return {
            "engagement_rate": sum(float(post.get(k) or 0) for k in
                                   ("likes", "replies", "reposts", "bookmarks", "quotes")) / imp,
            "like_rate": float(post.get("likes") or 0) / imp,
            "reply_rate": float(post.get("replies") or 0) / imp,
            "repost_rate": float(post.get("reposts") or 0) / imp,
            "bookmark_rate": float(post.get("bookmarks") or 0) / imp,
            "quote_rate": float(post.get("quotes") or 0) / imp,
        }
    rows=[(p,rates(p)) for p in posts]
    keys=("engagement_rate","like_rate","reply_rate","repost_rate","bookmark_rate","quote_rate")
    medians={k:median(r[k] for _,r in rows) for k in keys}
    top=sorted(rows,key=lambda x:x[1]["engagement_rate"],reverse=True)[:10]
    return {"post_count":len(posts),"medians":medians,
            "top_posts":[{"id":p["id"],"text":p["text"],"impressions":p.get("impressions",0),"features":r}
                         for p,r in top]}


def cleanup_duplicate_events() -> int:
    if not enabled():
        return 0
    init_db()
    removed = 0
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT cluster_key,array_agg(id ORDER BY latest_seen_at DESC) ids
                       FROM events WHERE cluster_key IS NOT NULL
                       GROUP BY cluster_key HAVING COUNT(*) > 1""")
        for key, ids in cur.fetchall():
            keep = ids[0]
            for old in ids[1:]:
                cur.execute("UPDATE content_opportunities SET event_id=%s WHERE event_id=%s", (keep, old))
                cur.execute("UPDATE event_analyses SET event_id=%s WHERE event_id=%s", (keep, old))
                cur.execute("DELETE FROM trend_signals WHERE event_id=%s", (old,))
                cur.execute("DELETE FROM events WHERE id=%s", (old,))
                removed += 1
        conn.commit()
    return removed


def recent_opportunities(limit: int = 20) -> list[dict[str, Any]]:
    if not enabled():
        return []
    init_db()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,event_id,title,why_now,audience,angle,suggested_format,
                       priority,created_at,expires_at
                       FROM content_opportunities
                       ORDER BY priority DESC,created_at DESC LIMIT %s""",(limit,))
        cols=[d.name for d in cur.description]
        return [dict(zip(cols,row)) for row in cur.fetchall()]


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
