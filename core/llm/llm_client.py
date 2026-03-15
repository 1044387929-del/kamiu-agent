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


def get_llm():
    """LangGraph 用：LangChain ChatOpenAI。"""
    from langchain_community.chat_models import ChatOpenAI
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=DASHSCOPE_BASE,
        temperature=0.7,
    )
