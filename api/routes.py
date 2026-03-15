"""
助手 API：对话、流式回复等。
"""
from typing import Any

from fastapi import APIRouter
from langchain_core.messages import HumanMessage

from graph import get_graph

router = APIRouter()


@router.post("/chat")
def chat(body: dict[str, Any]) -> dict[str, Any]:
    """
    单轮对话（非流式）。
    请求体示例：{ "message": "用户输入", "teacher_id": "xxx", "history": [] }
    """
    message = (body.get("message") or "").strip()
    teacher_id = body.get("teacher_id") or ""
    history = body.get("history") or []

    messages = [HumanMessage(content=msg.get("content", "")) for msg in history]
    messages.append(HumanMessage(content=message))

    state = {
        "messages": messages,
        "teacher_id": teacher_id,
    }
    graph = get_graph()
    result = graph.invoke(state)

    out_messages = result.get("messages") or []
    last = out_messages[-1] if out_messages else None
    content = getattr(last, "content", "") if last else ""

    return {"reply": content}


@router.get("/chat")
def chat_get():
    """占位：GET 仅作健康或说明。"""
    return {"usage": "POST /api/chat with body: { message, teacher_id?, history? }"}
