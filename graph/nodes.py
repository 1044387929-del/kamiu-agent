"""
LangGraph 节点：每个节点接收 state，返回 state 的增量更新。
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from graph.state import AgentState


def route_node(state: AgentState) -> AgentState:
    """
    路由节点：根据最后一条用户消息决定下一步（可扩展为调用 LLM 做意图识别）。
    当前为占位：直接进入回复节点。
    """
    return {}


def reply_node(state: AgentState) -> AgentState:
    """
    回复节点：根据当前 state 生成助手回复（占位：简单 echo）。
    后续可在此调用 LLM，并注入 retrieved_docs、tool_results 等。
    """
    messages = state.get("messages") or []
    if not messages:
        return {"messages": [AIMessage(content="你好，我是教师助手。当前为占位回复。")]}
    last = messages[-1]
    if isinstance(last, HumanMessage):
        reply = f"收到你的消息（占位）：{last.content[:100]}…"
    else:
        reply = "请发送一条消息。"
    return {"messages": [AIMessage(content=reply)]}


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
