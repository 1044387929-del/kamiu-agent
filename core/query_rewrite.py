"""
轻量级 Query Rewrite：在进入 schema linking / Text2SQL 之前，把用户提问改写得更清晰、更结构化，
但必须严格保持语义等价（不新增/删减条件、不改变时间/数量范围），参考 DB-GPT 的 QueryRewrite 设计。
"""
from __future__ import annotations

from typing import Optional

from core.config import settings
from core.llm import get_openai_client


_REWRITE_SYSTEM_ZH = (
    "你是问题改写助手，负责在不改变语义的前提下，把用户的问题改写成更清晰、结构化、适合数据库查询理解的表述。\n"
    "严格要求：\n"
    "- 不得改变问题的主体、时间范围、数量范围或任何显式条件；不得引入原句里没有的表名、字段名或业务概念。\n"
    "- 可以：补全省略主语（如“他”改写为“前文提到的那位老师”）、补齐量词（如“最近十次讨论”保持为“最近十次讨论”），"
    "把口语式提问改写成更正式的书面语。\n"
    "- 输出只需一条改写后的单句问题，不要列出多个候选，也不要解释理由。\n"
)


def rewrite_question_if_enabled(
    question: str, context_hint: Optional[str] = None
) -> str:
    """若配置启用 QUERY_REWRITE，则调用大模型做一次改写；失败或被关闭则返回原问题。

    仅用于内部 schema linking / DB 路由，不回显给用户。
    """
    q = (question or "").strip()
    if not q:
        return q
    if not getattr(settings, "query_rewrite_enabled", False):
        return q

    client = get_openai_client()
    user_content = q
    if context_hint:
        user_content = f"上下文提示：{context_hint}\n原问题：{q}"

    try:
        completion = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM_ZH},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
        )
        text = (completion.choices[0].message.content or "").strip()
        # 防御：空输出或明显与原问题长度极不相称时，回退原文
        if not text:
            return q
        if len(text) > 3 * len(q) and len(q) > 0:
            return q
        return text
    except Exception:
        return q

