"""联网搜索工具。"""

from langchain_core.tools import tool

from core.config import settings
from core.llm import get_openai_client


@tool
def web_search(query: str) -> str:
    """在互联网上搜索实时或最新信息。请先尝试使用非联网工具；仅当无法解决时再调用本工具。"""
    client = get_openai_client()
    try:
        completion = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个联网搜索助手。根据用户问题搜索并返回简洁、准确的答案。",
                },
                {"role": "user", "content": query},
            ],
            extra_body={"enable_search": True},
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        return f"联网搜索失败：{e}"

