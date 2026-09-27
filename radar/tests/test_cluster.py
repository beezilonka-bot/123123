from datetime import datetime, timezone

from radar.cluster import cluster_items, score_events, similarity


def item(i, title, source="s1", published="2026-09-27T12:00:00+00:00"):
    return {
        "id": str(i), "title": title, "summary": title,
        "source_id": source, "published_at": published,
    }


def test_similarity_groups_same_event():
    assert similarity("Apple launches new AI chip", "Apple launches AI chip today") > 0.45


def test_cluster_groups_similar_headlines():
    events = cluster_items([
        item(1, "Apple launches new AI chip"),
        item(2, "Apple launches AI chip today", source="s2"),
        item(3, "Premier League match postponed"),
    ])
    assert len(events) == 2
    first = max(events, key=lambda e: e["item_count"])
    assert first["item_count"] == 2
    assert first["source_count"] == 2


def test_score_is_explainable_and_sorted():
    now = datetime(2026, 9, 27, 13, tzinfo=timezone.utc)
    events = cluster_items([
        item(1, "Apple launches new AI chip", published="2026-09-27T12:00:00+00:00"),
        item(2, "Apple launches AI chip today", source="s2", published="2026-09-27T12:30:00+00:00"),
        item(3, "Old unrelated story", published="2026-09-25T00:00:00+00:00"),
    ])
    scored = score_events(events, topics=["AI chip"], now=now)
    assert scored[0]["trend_signal"]["total_score"] >= scored[-1]["trend_signal"]["total_score"]
    assert "freshness" in scored[0]["trend_signal"]
