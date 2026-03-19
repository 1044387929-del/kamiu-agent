"""
LLM 意图路由：把用户问题归类为（是否需要 DB/是否强制查库/是否需要联网等）。

设计理念参考 DB-GPT 的 IntentRecognition：输出结构化 JSON，便于后续流程严格执行。
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage

from core.config import settings
from core.llm import get_openai_client
from graph.state import AgentState


_SYSTEM = (
    "你是意图路由器。根据用户问题，输出严格 JSON，用于决定是否需要调用外挂工具。\n"
    "规则：\n"
    "- 仅当问题需要平台内部数据验证（新增/是否有/数量/统计/明细等）时，enable_db_query=true。\n"
    "- 若属于平台内部可验证且用户明确询问“有没有/多少/是否新增/某天数据”，force_db_query=true（必须查库，不允许口头推断）。\n"
    "- enable_web_search 不由你决定（由前端开关决定），你只输出 web_search_recommended（true/false）。\n"
    "输出 JSON schema：\n"
    "{\n"
    "  \"enable_db_query\": true/false,\n"
    "  \"force_db_query\": true/false,\n"
    "  \"web_search_recommended\": true/false,\n"
    "  \"reason\": \"一句话理由\"\n"
    "}\n"
    "只输出 JSON，不要输出其它文字。"
)


def _last_user_text(state: AgentState) -> str:
    for m in reversed(state.get("messages") or []):
        if isinstance(m, HumanMessage):
            return (m.content or "").strip()
    return ""


def llm_route(state: AgentState) -> dict[str, Any]:
    question = _last_user_text(state)
    if not question:
        return {"enable_db_query": False, "force_db_query": False, "web_search_recommended": False}

    client = get_openai_client()
    model = (state.get("model") or "").strip() or settings.llm_model
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
        )
        text = (completion.choices[0].message.content or "").strip()
        data = json.loads(text)
        return {
            "enable_db_query": bool(data.get("enable_db_query", False)),
            "force_db_query": bool(data.get("force_db_query", False)),
            "web_search_recommended": bool(data.get("web_search_recommended", False)),
        }
    except Exception:
        return {"enable_db_query": False, "force_db_query": False, "web_search_recommended": False}

