"""
基于 LangGraph 的对话：带工具调用（如 get_current_time），支持思考模式返回 reasoning。
"""
from langchain_core.messages import AIMessage, HumanMessage

from core.config import settings
from core.schemas.chat import ChatRequest, ChatResponse
from graph.graph import get_graph


def chat_request_to_messages(req: ChatRequest) -> list:
    """将 ChatRequest 转为 LangChain messages（HumanMessage / AIMessage）。"""
    messages = []
    history = req.history or []
    for i, h in enumerate(history):
        content = (h.get("content") or "").strip()
        if not content:
            continue
        if i % 2 == 0:
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=(req.message or "").strip()))
    return messages


def chat_with_agent(req: ChatRequest) -> ChatResponse:
    """走图执行对话（含工具），返回最终回复；若开启思考模式则带 reasoning。"""
    messages = chat_request_to_messages(req)
    if not messages:
        return ChatResponse(reply="你好，我是教师助手。有什么可以帮你的？")
    enable_thinking = (
        req.enable_thinking if req.enable_thinking is not None else settings.enable_thinking_default
    )
    graph = get_graph()
    result = graph.invoke({"messages": messages, "enable_thinking": enable_thinking})
    final_messages = result.get("messages") or []
    reply = ""
    for m in reversed(final_messages):
        if hasattr(m, "content") and getattr(m, "content", None):
            reply = (m.content or "").strip()
            break
    reasoning = result.get("last_reasoning")
    return ChatResponse(reply=reply or "抱歉，没有生成回复。", reasoning=reasoning)

