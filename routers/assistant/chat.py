"""助手对话接口：非流式 / 流式 SSE"""
from openai import OpenAI
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.deps import get_client
from core.schemas.chat import ChatRequest, ChatResponse
from core.llm import chat_completion, chat_completion_stream

router = APIRouter(tags=["chat"])


@router.get("/chat")
def chat_get() -> dict:
    """说明。"""
    return {
        "usage": "POST /api/chat 或 POST /api/chat/stream",
        "body": {
            "message": "必填",
            "history": "[]",
            "teacher_id": "",
            "enable_thinking": "false",
            "model": "可选",
        },
    }


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    client: OpenAI = Depends(get_client),
) -> ChatResponse:
    """单轮对话（非流式）。"""
    return chat_completion(client, body)


@router.post("/chat/stream")
def chat_stream(
    body: ChatRequest,
    client: OpenAI = Depends(get_client),
) -> StreamingResponse:
    """流式对话（SSE），事件类型：reasoning | content | usage | done。"""
    return StreamingResponse(
        chat_completion_stream(client, body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
