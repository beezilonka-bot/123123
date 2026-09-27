"""One-click X post generation using the configured OpenAI-compatible LLM."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .analyzer import _llm_config


def _clip(value: Any, limit: int = 1800) -> str:
    return str(value or "").strip()[:limit]


def _build_prompt(request: dict[str, Any], context: dict[str, Any]) -> str:
    history = context.get("history") or []
    opportunities = context.get("opportunities") or []
    history_text = "\n".join(
        f"- {_clip(x.get('text'), 500)}" for x in history[:8] if x.get("text")
    ) or "(没有可用的历史推文)"
    opp_text = "\n".join(
        f"- {x.get('title','')} | 角度: {_clip(x.get('angle'), 400)}"
        for x in opportunities[:5]
    ) or "(没有可用的 Radar 机会)"
    return f"""你是 X 长期创作者的写作助手。你的任务是根据用户输入和已有上下文，生成一条可直接编辑发布的中文或英文 X 帖子。

硬性要求：
1. 不编造事实、数字、人物言论或来源；只能把用户输入、已提供的 Radar 上下文或明确给出的历史内容当作事实依据。
2. 如果只是一般性推理或观点，明确写成观点，不要包装成统计结论；如果 mode=url，当前没有抓取网页正文时，不得声称知道网页具体内容。
3. 保持自然、具体、有信息密度，避免模板化的“作为AI”“值得关注的是”等套话。
4. 优先保留用户自己的观点；不要擅自改变立场。
5. 默认单条帖子，目标长度不超过 280 个英文字符或约 180 个中文字符；必要时可以略短。
6. 如果输入涉及政治、选举、公共政策或候选人，只做中性事实陈述和观点整理，不提供投票、支持或反对建议。
7. 只返回 JSON，不要 Markdown 代码围栏。

用户请求：
{json.dumps(request, ensure_ascii=False)}

用户历史推文（用于学习表达习惯，不复制原文）：
{history_text}

Radar 内容机会（仅作事实和角度参考）：
{opp_text}

输出字段：
post: string（最终帖子）
alternatives: string array（最多2条不同写法）
angle: string
facts_used: string array（最多5条）
uncertainty: string
"""


def _call(prompt: str) -> dict[str, Any] | None:
    key, base, model = _llm_config()
    if not key:
        return None
    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        post = _clip(parsed.get("post"), 1200)
        if not post:
            return None
        return {
            "post": post,
            "alternatives": [_clip(x, 1200) for x in parsed.get("alternatives", [])[:2]],
            "angle": _clip(parsed.get("angle"), 500),
            "facts_used": [str(x)[:500] for x in parsed.get("facts_used", [])[:5]],
            "uncertainty": _clip(parsed.get("uncertainty"), 1000),
            "model": model,
        }
    except Exception as exc:
        return {"_error": str(exc)}


def generate_post(request: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    result = _call(_build_prompt(request, context))
    if not result:
        return {"ok": False, "error": "llm_unavailable"}
    if "_error" in result:
        return {"ok": False, "error": "llm_generation_failed", "detail": result["_error"]}
    return {"ok": True, **result}