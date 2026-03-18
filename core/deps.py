"""
FastAPI 依赖注入。
"""
from openai import OpenAI

from core.llm import get_openai_client


def get_client() -> OpenAI:
    """注入 OpenAI 客户端。"""
    return get_openai_client()
