"""时间相关工具。"""

from langchain_core.tools import tool


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

