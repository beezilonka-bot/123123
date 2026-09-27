import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from radar.collector import collect_feed


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
            feed = os.getenv("TEST_FEED_URL", "https://feeds.bbci.co.uk/news/rss.xml")
            try:
                items = collect_feed(feed, "bbc-news", "BBC News")
                return self._json(200, {"ok": True, "count": len(items), "items": items[:20]})
            except Exception as exc:
                return self._json(502, {"ok": False, "error": str(exc)})
        return self._json(404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt, *args):
        print(fmt % args)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
