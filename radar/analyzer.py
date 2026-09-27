"""LLM-backed event analysis with deterministic fallback.

Uses an OpenAI-compatible /chat/completions endpoint when configured.
No API key is stored in source code.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any


def _fallback(event: dict[str, Any]) -> dict[str, Any]:
    title = (event.get("title") or "").strip()
    summary = (event.get("summary") or "").strip()
    signal = event.get("trend_signal") or {}
    score = event.get("total_score", signal.get("total_score", 0)) or 0
    items = event.get("items") or []
    facts = [x.get("title") for x in items[:5] if x.get("title")]
    if not facts and title:
        facts = [title]
    if summary and summary not in facts:
        facts.append(summary)
    return {
        "event_id": event["id"], "importance": min(100, round(float(score))),
        "why_it_matters": f"当前来自 {event.get('source_count', 0)} 个来源、{event.get('item_count', 0)} 条相关报道；需要结合原始报道核实具体影响。",
        "who_cares": "关注该主题的用户、行业参与者及相关决策者。",
        "key_facts": facts[:5],
        "uncertainty": "当前分析基于标题与 RSS 摘要，尚未进行全文事实核验。",
        "tags": [], "suggested_angles": [
            "发生了什么，以及这次变化与此前有什么不同。",
            "为什么现在值得关注，以及接下来需要观察什么。",
        ],
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "model": "deterministic-v2",
    }


def _llm_config() -> tuple[str | None, str, str]:
    key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
    return key, base, model


def _prompt(event: dict[str, Any]) -> str:
    items = event.get("items") or []
    reports = "\n".join(
        f"- {x.get('title','')} | {x.get('summary') or ''}" for x in items[:8]
    )
    return f"""你是一个新闻信息分析器，不是内容营销人员。
请基于下面的事件和RSS信息，输出严格JSON。
目标：判断发生了什么、为什么现在值得关注、谁会关心，以及适合进一步研究的内容角度。
不要编造事实；无法确认的信息放入 uncertainty。
政治、选举、公共政策等话题必须保持中立，不提供投票或政治选择建议。

事件：
标题：{event.get('title','')}
摘要：{event.get('summary') or ''}
趋势分数：{event.get('total_score', 0)}
来源数：{event.get('source_count', 0)}
报道数：{event.get('item_count', 0)}

相关报道：
{reports}

JSON字段必须为：
importance (0-100),
why_it_matters (string),
who_cares (string),
key_facts (string array, max 5),
uncertainty (string),
tags (string array, max 8),
suggested_angles (string array, max 3)
"""


def _call_llm(event: dict[str, Any]) -> dict[str, Any] | None:
    key, base, model = _llm_config()
    if not key:
        return None
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": _prompt(event)},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        parsed["event_id"] = event["id"]
        parsed["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        parsed["model"] = model
        parsed["importance"] = max(0, min(100, round(float(parsed.get("importance", 0)))))
        parsed["key_facts"] = list(parsed.get("key_facts", []))[:5]
        parsed["tags"] = list(parsed.get("tags", []))[:8]
        parsed["suggested_angles"] = list(parsed.get("suggested_angles", []))[:3]
        return parsed
    except Exception:
        return None


def llm_configured() -> bool:
    return bool(_llm_config()[0])


def analyze_event(event: dict[str, Any]) -> dict[str, Any]:
    """Use LLM when configured; otherwise return a safe deterministic result."""
    return _call_llm(event) or _fallback(event)
