"""
领域/实体配置：统一描述“学生/教师/讨论/班级”等业务实体对应的表与检索关键词。

参考 DB-GPT：将「哪些表属于哪类实体、如何触发」从代码中抽离为配置，便于扩展与维护。
新增实体时只需在此增加一项，无需在 route/schema_link/nodes 里打补丁。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class EntityConfig:
    """单个业务实体的配置。"""

    id: str  # 实体标识，如 student, teacher, discussion
    # 用户问题中出现任一词即认为涉及该实体，用于路由与 schema 扩展
    query_keywords: tuple[str, ...]
    # schema 块内容中出现任一词即纳入候选（表名/字段名/注释）
    block_keywords: tuple[str, ...]
    # 给 agent 的简短提示：该实体对应哪些表、如何查
    prompt_hint: str = ""


# 平台当前支持的实体配置（可按需扩展）
ENTITY_CONFIGS: tuple[EntityConfig, ...] = (
    EntityConfig(
        id="student",
        query_keywords=("学生", "姓名", "某人", "谁", "有没有", "是否存在", "叫什么"),
        block_keywords=("学生", "student", "姓名", "student_name", "first_name", "last_name"),
        prompt_hint="若涉及“学生”“某人是否存在”“按姓名查”：须同时查 accounts（user_type=student、first_name/last_name/username）与 school_student（学生档案 student_name），在所有相关表都查询后再下结论。",
    ),
    EntityConfig(
        id="teacher",
        query_keywords=("老师", "教师", "的id", "的 id", "teacher"),
        block_keywords=("老师", "教师", "teacher", "teacher_id", "teacher_name", "school_teacher"),
        prompt_hint="若涉及“老师”“教师”“某老师的id”或“相关讨论”：须同时考虑 school_teacher（教师档案 teacher_id、teacher_name）、school_class_teacher（班级-教师关联）及讨论相关表，不可只根据部分表就断言查不到。",
    ),
    EntityConfig(
        id="discussion",
        query_keywords=("讨论", "帖子", "贴子", "话题", "场", "场次", "几场", "组织"),
        block_keywords=("讨论", "discussion", "discussions", "帖子", "topic", "teacher_id"),
        prompt_hint="若涉及“讨论”“场次”“谁组织的”：使用 discussions 等表，按 teacher_id 或组织者字段统计；须先查清主体（如老师）的 id 再统计。",
    ),
    EntityConfig(
        id="class",
        query_keywords=("班级", "班"),
        block_keywords=("班级", "class", "school_class", "class_id"),
        prompt_hint="若涉及“班级”：参考 school_class、school_class_teacher 等表。",
    ),
)


def get_entity_configs() -> Sequence[EntityConfig]:
    """返回所有实体配置（只读）。"""
    return ENTITY_CONFIGS


def get_entity_by_id(entity_id: str) -> EntityConfig | None:
    """按 id 获取单个实体配置。"""
    for e in ENTITY_CONFIGS:
        if e.id == entity_id:
            return e
    return None


def infer_entity_types_from_question(question: str) -> list[str]:
    """根据用户问题推断涉及的实体类型（用于路由与 schema 扩展）。"""
    if not (question or question.strip()):
        return []
    q = question.strip().lower()
    out: list[str] = []
    for e in ENTITY_CONFIGS:
        if any(k in question or k.lower() in q for k in e.query_keywords):
            out.append(e.id)
    return out


def expand_blocks_by_entity_types(
    blocks: list[str],
    entity_types: Sequence[str],
    seen: set[str],
    candidates: list[str],
    max_blocks: int,
) -> None:
    """根据 entity_types 将匹配的 schema 块加入 candidates（原地修改）。"""
    entity_ids = set(entity_types or [])
    if not entity_ids:
        return
    for e in ENTITY_CONFIGS:
        if e.id not in entity_ids:
            continue
        for blk in blocks:
            if len(candidates) >= max_blocks:
                return
            key = (blk or "").strip()
            if not key or key in seen:
                continue
            blk_lower = key.lower()
            if any(k in key or k.lower() in blk_lower for k in e.block_keywords):
                seen.add(key)
                candidates.append(key)


def get_db_instruction_hints(entity_types: Sequence[str]) -> str:
    """根据涉及实体拼接给 agent 的 DB 查询提示（多表/多来源说明）。"""
    if not entity_types:
        return ""
    parts: list[str] = []
    for e in ENTITY_CONFIGS:
        if e.id in (entity_types or []):
            parts.append(e.prompt_hint)
    return " ".join(parts) if parts else ""
