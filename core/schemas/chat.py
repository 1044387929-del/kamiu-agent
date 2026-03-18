"""
对话接口的请求与响应模型。
"""
from typing import Any

from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """
    请求体：
    {
        "message": "用户输入",
        "history": "历史消息 [{content}]",
        "teacher_id": "教师 ID，预留",
        "enable_thinking": "是否开启思考模式，不传则用配置默认",
        "model": "模型名，不传则用配置默认"
    }
    这个类是请求体的模型，用于验证请求体的格式和类型。
    """
    # 用户输入，省略号表示必填
    message: str = Field(..., description="用户输入")
    # 历史消息，默认空列表
    history: list[dict[str, Any]] = Field(default_factory=list, description="历史消息 [{content}]")
    # 教师 ID，预留，默认空字符串
    teacher_id: str = Field(default="", description="教师 ID，预留")
    # 是否开启思考模式，不传则用配置默认，默认 None
    enable_thinking: bool | None = Field(default=None, description="是否开启思考模式，不传则用配置默认")
    # 是否开启联网搜索；开启后 agent 优先用非联网工具，解决不了再调用 web_search
    enable_web_search: bool = Field(default=False, description="是否开启联网搜索")
    # 模型名，不传则用配置默认
    model: str | None = Field(default=None, description="模型名，不传则用配置默认")


class ChatResponse(BaseModel):
    """
    响应体：
    {
        "reply": "助手回复",
        "reasoning": "思考过程，仅 enable_thinking 时可能有"
    }
    这个类是响应体的模型，用于验证响应体的格式和类型。
    """
    # 助手回复，省略号表示必填
    reply: str = Field(..., description="助手回复")
    # 思考过程，仅 enable_thinking 时可能有，默认 None
    reasoning: str | None = Field(default=None, description="思考过程，仅 enable_thinking 时可能有")
