"""
对话接口的请求与响应模型。
"""
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入")
    history: list[dict[str, Any]] = Field(default_factory=list, description="历史消息 [{content}]")
    teacher_id: str = Field(default="", description="教师 ID，预留")
    enable_thinking: bool | None = Field(default=None, description="是否开启思考模式，不传则用配置默认")
    model: str | None = Field(default=None, description="模型名，不传则用配置默认")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="助手回复")
    reasoning: str | None = Field(default=None, description="思考过程，仅 enable_thinking 时可能有")
