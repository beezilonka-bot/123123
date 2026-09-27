import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from radar.cluster import cluster_items, score_events
from radar.collector import collect_feed


def build_radar():
    feed = os.getenv("TEST_FEED_URL", "https://feeds.bbci.co.uk/news/rss.xml")
    topics = [x.strip() for x in os.getenv("RADAR_TOPICS", "").split(",") if x.strip()]
    items = collect_feed(feed, "bbc-news", "BBC News")
    events = cluster_items(items)
    ranked = score_events(events, topics=topics)
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
        "item_count": len(items),
        "event_count": len(ranked),
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
            return self._json(200, {"ok": True, "service": "123123-radar"})
        if path == "/feed":
            try:
                feed = os.getenv("TEST_FEED_URL", "https://feeds.bbci.co.uk/news/rss.xml")
                items = collect_feed(feed, "bbc-news", "BBC News")
                return self._json(200, {"ok": True, "count": len(items), "items": items[:20]})
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
