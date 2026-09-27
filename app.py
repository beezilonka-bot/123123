import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from radar.analyzer import analyze_event
from radar.cluster import cluster_items, score_events
from radar.collector import collect_feed
from radar.storage import enabled as db_enabled, persist_run, recent_events

DEFAULT_FEEDS = [
    ("bbc-news", "BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("npr-news", "NPR News", "https://feeds.npr.org/1001/rss.xml"),
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
    ranked = score_events(cluster_items(items), topics=topics)
    persisted = {"persisted_sources": 0, "persisted_items": 0, "persisted_events": 0}
    if db_enabled():
        sources = [{"id":sid,"name":name,"url":url,"type":"rss"}
                   for sid,name,url in configured_feeds()]
        persisted = persist_run(sources, items, ranked)
    return {"ok": not errors, "items": len(items), "events": len(ranked),
            "collection_errors": errors, "persistence": persisted}

def radar_response():
    if db_enabled():
        events = recent_events(30)
        return {"ok": True, "database_enabled": True, "source_count": len(configured_feeds()),
                "event_count": len(events),
                "opportunities": [
                    {"rank": i, "event_id": e["id"], "title": e["title"],
                     "why_now": f"score={float(e['total_score'] or 0):.2f}; "
                                f"{e['item_count']} reports / {e['source_count']} sources",
                     "audience": "general",
                     "angle": "Explain what changed, why it matters, and what to watch next.",
                     "suggested_format": "single_post",
                     "priority": float(e["total_score"] or 0),
                     "analysis": analyze_event(e)}
                    for i,e in enumerate(events[:10], 1)]}
    items, errors = collect_all_feeds()
    ranked = score_events(cluster_items(items))
    return {"ok": True, "database_enabled": False, "source_count": len(configured_feeds()),
            "item_count": len(items), "event_count": len(ranked), "collection_errors": errors,
            "opportunities": [{"rank":i,"event_id":e["id"],"title":e["title"],
                               "priority":e["trend_signal"]["total_score"],
                               "analysis":analyze_event(e)}
                              for i,e in enumerate(ranked[:10],1)]}

class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/health":
                return self._json(200, {"ok": True, "service": "123123-radar",
                                        "database_enabled": db_enabled()})
            if path == "/feed":
                items, errors = collect_all_feeds()
                return self._json(200, {"ok": True, "count": len(items),
                                        "collection_errors": errors, "items": items[:40]})
            if path == "/collect":
                return self._json(200, collect_and_persist())
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
