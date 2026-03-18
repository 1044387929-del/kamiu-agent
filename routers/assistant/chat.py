"""助手对话接口：统一走 Agent 图+工具；流式仅为返回形式（POST /api/chat/stream）。"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from core.schemas.chat import ChatRequest, ChatResponse
from core.agent import chat_with_agent, chat_with_agent_stream
from core.dashscope_models import get_model_list

router = APIRouter(tags=["chat"])


@router.get("/models")
def list_models() -> dict:
    """返回千问/DashScope 可用模型列表，供前端下拉选择。"""
    return {"models": get_model_list()}


@router.get("/chat")
def chat_get() -> dict:
    """说明。"""
    return {
        "usage": "POST /api/chat（JSON）或 POST /api/chat/stream（SSE），均走 Agent 图+工具",
        "body": {
            "message": "必填",
            "history": "[]",
            "teacher_id": "",
            "enable_thinking": "false",
            "enable_web_search": "false，是否联网搜索",
            "model": "可选",
        },
    }


# 统一走 Agent 图；stream 仅控制返回形式
@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """非流式：经 Agent 图（含工具），返回 JSON。"""
    return chat_with_agent(body)


@router.post("/chat/stream")
def chat_stream(body: ChatRequest) -> StreamingResponse:
    """流式（SSE）：经同一 Agent 图（含工具），结果按 content/reasoning/done 流式返回。"""
    return StreamingResponse(
        chat_with_agent_stream(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
