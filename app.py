import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from radar.analyzer import analyze_event, llm_configured
from radar.cluster import cluster_items, score_events
from radar.collector import collect_feed
from radar.x_import import parse_payload

from radar.storage import (
    enabled as db_enabled,
    persist_analysis,
    persist_run,
    recent_analyses,
    recent_events,
    recent_opportunities,
    record_opportunity,
    velocity_history,
    cleanup_duplicate_events,
    persist_account_posts,
    account_posts,
    summarize_account_performance,
    account_topic_profile,
    account_topic_relevance,
)

DEFAULT_FEEDS = [
    ("bbc-news", "BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("npr-news", "NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("techcrunch", "TechCrunch", "https://techcrunch.com/feed/"),
    ("the-verge", "The Verge", "https://www.theverge.com/rss/index.xml"),
]


def configured_feeds():
    raw = os.getenv("RADAR_FEEDS", "").strip()
    if not raw:
        return DEFAULT_FEEDS
    return [(f"feed-{i}", f"Feed {i}", u.strip())
            for i, u in enumerate(raw.split(","), 1) if u.strip()]


def collect_all_feeds():
    items, errors = [], []
    for sid, name, url in configured_feeds():
        try:
            items.extend(collect_feed(url, sid, name))
        except Exception as exc:
            errors.append({"source_id": sid, "error": str(exc)})
    return items, errors


def collect_and_persist():
    topics = [x.strip() for x in os.getenv("RADAR_TOPICS", "").split(",") if x.strip()]
    items, errors = collect_all_feeds()
    if db_enabled():
        cleanup_duplicate_events()
    history = velocity_history() if db_enabled() else {}
    ranked = score_events(cluster_items(items), topics=topics, history=history)
    persisted = {"persisted_sources": 0, "persisted_items": 0, "persisted_events": 0}
    analyses = 0
    limit = max(0, int(os.getenv("RADAR_LLM_LIMIT", "5")))
    profile = account_topic_profile(account_posts(1000)) if db_enabled() else {"top_terms": []}
    if db_enabled():
        sources = [{"id":sid, "name":name, "url":url, "type":"rss"}
                   for sid, name, url in configured_feeds()]
        persisted = persist_run(sources, items, ranked)
        for event in ranked[:limit]:
            analysis = analyze_event(event)
            persist_analysis(analysis)
            angles = analysis.get("suggested_angles") or []
            angle = angles[0] if angles else "解释发生了什么、为什么重要，以及接下来观察什么。"
            opportunity = {
                "id": f"op-{event['id']}",
                "event_id": event["id"],
                "title": event["title"],
                "why_now": analysis.get("why_it_matters"),
                "audience": analysis.get("who_cares"),
                "angle": angle,
                "suggested_format": "single_post",
                "priority": round(
                    float(analysis.get("importance", 0)) * 0.75 +
                    account_topic_relevance(event["title"], profile) * 25.0, 2),
            }
            record_opportunity(opportunity)
            analyses += 1
    return {
        "ok": not errors,
        "items": len(items),
        "events": len(ranked),
        "llm_configured": llm_configured(),
        "llm_analyses": analyses,
        "collection_errors": errors,
        "persistence": persisted,
    }


def radar_response():
    if db_enabled():
        events = recent_events(30)
        analyses = recent_analyses(20)
        stored = recent_opportunities(20)
        opportunities = []
        profile = account_topic_profile(account_posts(1000))
        for i, event in enumerate(events[:10], 1):
            analysis = analyses.get(event["id"]) or {"event_id": event["id"], "importance": 0, "why_it_matters": None, "who_cares": "general", "suggested_angles": []}
            account_relevance = account_topic_relevance(event["title"], profile)
            opportunities.append({
                "rank": i,
                "event_id": event["id"],
                "title": event["title"],
                "why_now": f"score={float(event['total_score'] or 0):.2f}; "
                           f"{event['item_count']} reports / {event['source_count']} sources",
                "audience": analysis.get("who_cares", "general"),
                "angle": (analysis.get("suggested_angles") or
                          ["Explain what changed, why it matters, and what to watch next."])[0],
                "suggested_format": "single_post",
                "priority": round(float(event["total_score"] or 0) * 0.8 + account_relevance * 20.0, 2),
                "account_relevance": round(account_relevance, 4),
                "analysis": analysis,
            })
        return {
            "ok": True,
            "database_enabled": True,
            "stored_opportunities": stored,
            "llm_configured": llm_configured(),
            "source_count": len(configured_feeds()),
            "event_count": len(events),
            "opportunities": opportunities,
        }
    items, errors = collect_all_feeds()
    ranked = score_events(cluster_items(items))
    return {
        "ok": True,
        "database_enabled": False,
        "llm_configured": llm_configured(),
        "source_count": len(configured_feeds()),
        "item_count": len(items),
        "event_count": len(ranked),
        "collection_errors": errors,
        "opportunities": [
            {"rank":i, "event_id":e["id"], "title":e["title"],
             "priority":e["trend_signal"]["total_score"],
             "analysis":analyze_event(e)}
            for i, e in enumerate(ranked[:10], 1)
        ],
    }


class Handler(BaseHTTPRequestHandler):
    def _authorized(self, header_name="X-Radar-Token"):
        expected = os.getenv("RADAR_ADMIN_TOKEN", "").strip()
        if not expected:
            return False
        return self.headers.get(header_name, "") == expected

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/account/import":
            return self._json(404, {"ok": False, "error": "not_found"})
        if not db_enabled():
            return self._json(503, {"ok": False, "error": "database_disabled"})
        if not self._authorized():
            return self._json(401, {"ok": False, "error": "unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 5_000_000:
                return self._json(400, {"ok": False, "error": "body must be 1 byte to 5 MB"})
            body = self.rfile.read(length)
            query = parse_qs(parsed.query)
            content_type = self.headers.get("Content-Type", "").lower()
            fmt = (query.get("format") or [""])[0].lower()
            if not fmt:
                fmt = "json" if "json" in content_type else "csv"
            posts = parse_payload(body, fmt)
            count = persist_account_posts(posts)
            return self._json(200, {
                "ok": True,
                "format": fmt,
                "imported": count,
                "message": "Imported user-provided history; no X API was used.",
            })
        except Exception as exc:
            return self._json(400, {"ok": False, "error": str(exc)})

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/health":
                return self._json(200, {"ok": True, "service": "123123-radar",
                                        "database_enabled": db_enabled(),
                                        "llm_configured": llm_configured()})
            if path == "/feed":
                items, errors = collect_all_feeds()
                return self._json(200, {"ok": True, "count": len(items),
                                        "collection_errors": errors, "items": items[:40]})
            if path == "/collect":
                if not self._authorized():
                    return self._json(401, {"ok": False, "error": "unauthorized"})
                return self._json(200, collect_and_persist())
            if path == "/account/performance":
                posts = account_posts(1000)
                return self._json(200, {"ok": True, "performance": summarize_account_performance(posts)})
            if path == "/radar":
                return self._json(200, radar_response())
            return self._json(404, {"ok": False, "error": "not_found"})
        except Exception as exc:
            return self._json(502, {"ok": False, "error": str(exc)})

    def log_message(self, fmt, *args):
        print(fmt % args)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
