"""Agent 工具：时间、联网搜索等。"""
from langchain_core.tools import tool

from core.config import settings
from core.llm import get_openai_client


@tool
def get_current_time() -> str:
    """获取当前日期和时间。当用户问「现在几点」「今天几号」「当前时间」时使用。"""
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except ImportError:
        now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


@tool
def web_search(query: str) -> str:
    """在互联网上搜索实时或最新信息。当用户询问天气、新闻、实时事件、近期动态等无法用 get_current_time 等工具回答的问题时使用。请先尝试用其他工具；仅当其他工具无法解决时再调用本工具。"""
    client = get_openai_client()
    try:
        completion = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "你是一个联网搜索助手。根据用户问题搜索并返回简洁、准确的答案。"},
                {"role": "user", "content": query},
            ],
            extra_body={"enable_search": True},
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        return f"联网搜索失败：{e}"


def get_tools_list(enable_web_search: bool = False) -> list:
    """根据是否开启联网搜索返回工具列表。优先使用非联网工具，联网搜索仅在其他工具无法解决时使用。"""
    base = [get_current_time]
    if enable_web_search:
        return base + [web_search]
    return base


# 默认不包含联网搜索，兼容旧调用
tools_list = get_tools_list(False)
