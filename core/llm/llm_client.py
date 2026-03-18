"""
LLM 客户端：DashScope 兼容接口。
"""
from typing import Final

from openai import OpenAI

from core.config import settings

DASHSCOPE_BASE: Final[str] = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def get_openai_client() -> OpenAI:
    """对话接口用：支持 stream、enable_thinking。"""
    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=DASHSCOPE_BASE,
    )


def get_llm(model: str | None = None):
    """LangGraph 用：ChatOpenAI（需支持 bind_tools）。model 为 None 时使用配置默认。"""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model or settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=DASHSCOPE_BASE,
        temperature=0.7,
    )
