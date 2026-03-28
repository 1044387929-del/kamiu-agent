"""工具包入口：集中“注册/组装”工具列表。

约定：
- 各类工具按领域拆分到独立模块（如 time/web/db）
- 本文件仅负责导入与按开关拼装 tools_list（便于 LangGraph ToolNode 注入）
"""

from tools.db import (
    execute_readonly_sql,
    get_db_schema,
    repair_sql,
)
from tools.time import get_current_time
from tools.web import web_search


def get_tools_list(
    enable_web_search: bool = False,
    enable_db_query: bool = False,
) -> list:
    """根据开关返回工具列表。优先使用非联网、非 DB 工具；联网/DB 仅在其他工具无法解决或用户明确查数时使用。"""
    base = [get_current_time]
    if enable_db_query:
        base = base + [
            get_db_schema,
            execute_readonly_sql,
            repair_sql,
        ]
    if enable_web_search:
        base = base + [web_search]
    return base


# 默认不包含联网与 DB 查询，兼容旧调用
tools_list = get_tools_list(False, False)
