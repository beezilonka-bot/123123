"""Scheduled radar collection entrypoint."""
from radar.cluster import cluster_items, score_events
from radar.collector import collect_feed
from radar.storage import enabled, persist_run
from app import configured_feeds


def main():
    items = []
    errors = []
    feeds = configured_feeds()
    for source_id, source_name, url in feeds:
        try:
            items.extend(collect_feed(url, source_id, source_name))
        except Exception as exc:
            errors.append({"source_id": source_id, "error": str(exc)})
    if errors:
        raise RuntimeError(f"collection errors: {errors}")
    events = score_events(cluster_items(items))
    if enabled():
        sources = [{"id": sid, "name": name, "url": url, "type": "rss"}
                   for sid, name, url in feeds]
        print(persist_run(sources, items, events))
    else:
        print({"database_enabled": False, "items": len(items), "events": len(events)})


if __name__ == "__main__":
    main()
