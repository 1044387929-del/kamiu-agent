"""
LangGraph 状态定义：图中节点间共享的数据。
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """助手图的状态。"""

    # 对话消息（可由 add_messages 做增量追加）
    messages: Annotated[list, add_messages]
    # 当前教师 ID（由调用方注入，用于权限）
    teacher_id: str
    # 当前教师可见的 discussion_id 列表（可选，由 Django 下发）
    allowed_discussion_ids: list[str]
    # 当前选中的讨论 ID（若从讨论详情页打开助手）
    current_discussion_id: str | None
    # 检索到的学科/知识库内容（RAG 结果）
    retrieved_docs: list[str]
    # 工具执行结果（如查数、画图）
    tool_results: dict
    # 是否开启思考模式（由调用方注入）
    enable_thinking: bool
    # 最近一次助手回复的思考过程（仅 enable_thinking 时由 agent 节点写入）
    last_reasoning: str | None
