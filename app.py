import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from radar.cluster import cluster_items, score_events
from radar.collector import collect_feed
from radar.storage import enabled as db_enabled, persist_run

DEFAULT_FEEDS = [
    ("bbc-news", "BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("npr-news", "NPR News", "https://feeds.npr.org/1001/rss.xml"),
]


def configured_feeds():
    raw = os.getenv("RADAR_FEEDS", "").strip()
    if not raw:
        return DEFAULT_FEEDS
    feeds = []
    for index, url in enumerate(raw.split(","), start=1):
        url = url.strip()
        if url:
            feeds.append((f"feed-{index}", f"Feed {index}", url))
    return feeds


def collect_all_feeds():
    items = []
    errors = []
    for source_id, source_name, url in configured_feeds():
        try:
            items.extend(collect_feed(url, source_id, source_name))
        except Exception as exc:
            errors.append({"source_id": source_id, "error": str(exc)})
    return items, errors


def build_radar():
    topics = [x.strip() for x in os.getenv("RADAR_TOPICS", "").split(",") if x.strip()]
    items, errors = collect_all_feeds()
    events = cluster_items(items)
    ranked = score_events(events, topics=topics)

    persisted = {"persisted_sources": 0, "persisted_items": 0, "persisted_events": 0}
    if db_enabled() and not errors:
        sources = [
            {"id": source_id, "name": source_name, "url": url, "type": "rss"}
            for source_id, source_name, url in configured_feeds()
        ]
        persisted = persist_run(sources, items, ranked)

    opportunities = []
    for rank, event in enumerate(ranked[:10], start=1):
        opportunities.append({
            "rank": rank,
            "event_id": event["id"],
            "title": event["title"],
            "why_now": (
                f"Freshness {event['trend_signal']['freshness']:.2f}; "
                f"{event['item_count']} report(s) from {event['source_count']} source(s)."
            ),
            "audience": "general",
            "angle": "Explain what changed, why it matters, and what to watch next.",
            "suggested_format": "single_post",
            "priority": event["trend_signal"]["total_score"],
        })
    return {
        "ok": True,
        "source_count": len(configured_feeds()),
        "item_count": len(items),
        "event_count": len(ranked),
        "database_enabled": db_enabled(),
        "persistence": persisted,
        "collection_errors": errors,
        "opportunities": opportunities,
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._json(200, {"ok": True, "service": "123123-radar", "database_enabled": db_enabled()})
        if path == "/feed":
            try:
                items, errors = collect_all_feeds()
                return self._json(200, {"ok": True, "count": len(items), "collection_errors": errors, "items": items[:40]})
            except Exception as exc:
                return self._json(502, {"ok": False, "error": str(exc)})
        if path == "/radar":
            try:
                return self._json(200, build_radar())
            except Exception as exc:
                return self._json(502, {"ok": False, "error": str(exc)})
        return self._json(404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt, *args):
        print(fmt % args)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
