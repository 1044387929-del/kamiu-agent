"""
LangGraph 节点：每个节点接收 state，返回 state 的增量更新。
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.llm import get_llm
from graph.state import AgentState


def route_node(state: AgentState) -> AgentState:
    """
    路由节点：根据最后一条用户消息决定下一步（可扩展为调用 LLM 做意图识别）。
    当前为占位：直接进入回复节点。
    """
    return {}


SYSTEM_PROMPT = "你是教师智能助手，回答简洁、专业、友好。"


def reply_node(state: AgentState) -> AgentState:
    """
    回复节点：调用 LLM 根据当前 messages 生成助手回复。
    """
    messages = state.get("messages") or []
    if not messages:
        return {"messages": [AIMessage(content="你好，我是教师助手。有什么可以帮你的？")]}
    llm = get_llm()
    # 首条为系统提示，便于模型保持角色
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
    response = llm.invoke(full_messages)
    content = getattr(response, "content", "") or ""
    return {"messages": [AIMessage(content=content)]}


def inject_system_node(state: AgentState) -> AgentState:
    """
    注入系统提示：在对话前插入角色与权限说明（可选）。
    """
    teacher_id = state.get("teacher_id") or ""
    system = (
        "你是教师智能助手。当前教师 ID：{teacher_id}。"
        "回答要简洁、专业。".format(teacher_id=teacher_id)
    )
    return {"messages": [SystemMessage(content=system)]}
