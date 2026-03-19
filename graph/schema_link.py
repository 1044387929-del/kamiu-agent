"""
Schema linking：根据用户问题从全量 schema 中筛选相关表/字段，减少 Text2SQL/ORM 生成偏差。

理念参考 DB-GPT：
- 先用检索/筛选得到“相关 schema”，再让模型生成 SQL/代码
"""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage

from core.config import settings
from core.llm import get_openai_client
from graph.state import AgentState
from tools.db import get_db_schema
from core.schema_vector_store import retrieve_schema_blocks, upsert_schema_blocks


_SCHEMA_LINK_SYSTEM = (
    "你是一个 schema linking 助手。你的任务是：从给定的数据库 schema 文本中，筛选出回答用户问题所需的最相关表/字段信息。"
    "输出要求：只输出精简后的 schema 片段，保持可读性（按表分块），不要输出无关解释。"
)

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*|[\u4e00-\u9fff]+")


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if t.strip()}


def _split_schema_blocks(full_schema: str) -> list[str]:
    """把全量 schema 按表/Model 块切分，便于检索 top-k。"""
    s = (full_schema or "").strip()
    if not s:
        return []
    # Django 内省格式：每块以 "Model:" 开头
    if "\nModel:" in s or s.startswith("Model:"):
        parts = re.split(r"\n(?=Model:\s)", s)
        return [p.strip() for p in parts if p.strip()]
    # INFORMATION_SCHEMA 回退格式：每块以 "Table:" 开头
    if "\nTable:" in s or s.startswith("Table:"):
        parts = re.split(r"\n(?=Table:\s)", s)
        return [p.strip() for p in parts if p.strip()]
    # 兜底：按双换行拆
    return [p.strip() for p in s.split("\n\n") if p.strip()]


def _rank_blocks(question: str, blocks: list[str], top_k: int = 10) -> list[str]:
    """简单 lexical 检索：按 token 重叠和长度惩罚打分，选 top_k 候选块。"""
    q_tokens = _tokenize(question)
    if not q_tokens or not blocks:
        return blocks[:top_k]
    scored = []
    for b in blocks:
        b_tokens = _tokenize(b)
        overlap = len(q_tokens & b_tokens)
        if overlap <= 0:
            continue
        # 轻微长度惩罚，避免超长块霸榜
        score = overlap / (1.0 + (len(b_tokens) ** 0.25))
        scored.append((score, b))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in scored[:top_k]] or blocks[:top_k]


def _get_last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return (m.content or "").strip()
    return ""


def schema_link_node(state: AgentState) -> AgentState:
    """当 enable_db_query=True 时运行：写入 schema_link。失败则回退为全量 schema（或 None）。"""
    if not state.get("enable_db_query", False):
        return {"schema_link": None}

    question = _get_last_user_text(state)
    if not question:
        return {"schema_link": None}

    # get_db_schema 是 StructuredTool，需用 invoke 调用
    full_schema = get_db_schema.invoke({"table_prefix": ""})
    blocks = _split_schema_blocks(full_schema)

    # 先尝试用“DB Summary 向量检索”召回候选（对齐 DB-GPT），失败则仅用 lexical top-k
    try:
        upsert_schema_blocks(full_schema_text=full_schema, blocks=blocks)
        vec_candidates = retrieve_schema_blocks(question, top_k=12)
    except Exception:
        vec_candidates = []

    lex_candidates = _rank_blocks(question, blocks, top_k=12)
    # 合并去重：优先向量召回，再补 lexical
    seen = set()
    candidates: list[str] = []
    for b in (vec_candidates + lex_candidates):
        key = (b or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(key)
        if len(candidates) >= 16:
            break

    # 业务扩展：问题涉及“学生/某人/姓名”时，强制加入含 学生/student/姓名/student_name 的表块，避免只看到 accounts 而漏掉 school_student
    _person_keywords = ("学生", "姓名", "某人", "谁", "有没有", "是否存在", "叫什么")
    _block_keywords = ("学生", "student", "姓名", "student_name", "first_name", "last_name")
    if any(k in question for k in _person_keywords):
        for blk in blocks:
            blk_lower = (blk or "").lower()
            blk_raw = blk or ""
            if any(k in blk_raw or k.lower() in blk_lower for k in _block_keywords):
                key = blk.strip()
                if key and key not in seen:
                    seen.add(key)
                    candidates.append(key)
                    if len(candidates) >= 20:
                        break
        # 保持顺序稳定：已有候选在前，新加的在后
        if len(candidates) > 16:
            candidates = candidates[:20]

    # 候选 schema 太长时截断（避免提示超长）
    schema_for_link = "\n\n".join(candidates)
    max_chars = 12000
    if len(schema_for_link) > max_chars:
        schema_for_link = schema_for_link[:max_chars]

    client = get_openai_client()
    model = (state.get("model") or "").strip() or settings.llm_model

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SCHEMA_LINK_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "schema_candidates": schema_for_link},
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.0,
        )
        linked = (completion.choices[0].message.content or "").strip()
        if linked:
            return {"schema_link": linked}
    except Exception:
        pass

    # 回退：若失败，至少把候选 schema 给到后续提示
    return {"schema_link": schema_for_link}

