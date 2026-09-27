"""Event analysis models and deterministic fallback analyzer.

The fallback keeps the radar useful before an LLM key is configured.
"""
from __future__ import annotations
from typing import Any

def analyze_event(event: dict[str, Any]) -> dict[str, Any]:
    title = (event.get("title") or "").strip()
    summary = (event.get("summary") or "").strip()
    items = event.get("items") or []
    facts = [x.get("title") for x in items[:5] if x.get("title")]
    source_count = event.get("source_count", 0)
    return {
        "event_id": event["id"],
        "importance": min(100, round(event.get("trend_signal", {}).get("total_score", 0))),
        "why_it_matters": (
            f"报道来自 {source_count} 个来源，当前有 {event.get('item_count', 0)} 条相关报道；"
            "需要结合原始报道核实具体影响。"
        ),
        "who_cares": "关注该主题的用户、行业参与者及相关决策者。",
        "key_facts": facts,
        "uncertainty": "当前分析基于标题与 RSS 摘要，尚未进行全文事实核验。",
        "tags": [],
        "suggested_angles": [
            "发生了什么，以及这次变化与此前有什么不同。",
            "为什么现在值得关注，以及接下来可能需要观察什么。",
        ],
        "analyzed_at": event.get("trend_signal", {}).get("calculated_at"),
        "model": "deterministic-v1",
    }
