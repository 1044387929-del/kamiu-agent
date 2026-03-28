"""
数据库只读工具：schema 获取、只读 SQL 执行、SQL 修复（只读）。

对齐 DB-GPT 理念：以 SQL 为中心，不执行 ORM 代码；强安全约束禁止任何写操作/多语句/危险函数。
"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.tools import tool

from core.config import settings
from core.llm import get_openai_client


@tool
def get_db_schema(table_prefix: str = "") -> str:
    """获取数据库表结构说明，供生成 SQL 时参考。建议在生成 SQL 前先调用本工具。

    table_prefix 可选，用于过滤表名（留空则返回所有表）。
    """
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.db_host,
            port=int(settings.db_port or 3306),
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with conn.cursor() as cur:
                like = f"%{table_prefix}%" if table_prefix else "%"
                cur.execute(
                    "SELECT c.TABLE_NAME, t.TABLE_COMMENT, c.COLUMN_NAME, c.DATA_TYPE, c.COLUMN_KEY, c.COLUMN_COMMENT "
                    "FROM INFORMATION_SCHEMA.COLUMNS c "
                    "JOIN INFORMATION_SCHEMA.TABLES t "
                    "  ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME "
                    "WHERE c.TABLE_SCHEMA = %s AND c.TABLE_NAME LIKE %s "
                    "ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION",
                    (settings.db_name, like),
                )
                rows = cur.fetchall()
            if not rows:
                return "未找到匹配的表。"
            from collections import defaultdict
            by_table: dict[str, dict[str, Any]] = defaultdict(lambda: {"comment": "", "cols": []})
            for r in rows:
                tname = r["TABLE_NAME"]
                tcomment = (r.get("TABLE_COMMENT") or "").strip()
                if tcomment and not by_table[tname]["comment"]:
                    by_table[tname]["comment"] = tcomment
                col = r["COLUMN_NAME"]
                dtype = r["DATA_TYPE"]
                ckey = (r.get("COLUMN_KEY") or "").strip()
                ccomment = (r.get("COLUMN_COMMENT") or "").strip()
                key_tag = " PK" if ckey.upper() == "PRI" else (f" {ckey}" if ckey else "")
                suffix = f" # {ccomment}" if ccomment else ""
                by_table[tname]["cols"].append(f"- {col} ({dtype}){key_tag}{suffix}")

            out_blocks: list[str] = []
            for t, info in sorted(by_table.items()):
                header = f"Table: {t}" + (f"  # {info['comment']}" if info["comment"] else "")
                cols = "\n".join(info["cols"])
                out_blocks.append(f"{header}\nColumns:\n{cols}")
            return "\n\n".join(out_blocks)
        finally:
            conn.close()
    except ImportError:
        return "未安装 pymysql；且未配置 Django，无法获取表结构。请配置 DJANGO_SETTINGS_MODULE 与 DJANGO_PROJECT_PATH，或安装 pymysql。"
    except Exception as e:
        return f"从数据库读取表结构失败: {e}"


# 只允许的 SQL 语句类型（白名单）
_SQL_READONLY_PREFIXES = ("select", "show", "describe", "desc", "explain")
_SQL_FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "replace",
    "alter",
    "drop",
    "truncate",
    "create",
    "rename",
    "grant",
    "revoke",
    "commit",
    "rollback",
    "set",
    "use",
    "load",
    "outfile",
    "infile",
    "call",
    "execute",
    "prepare",
    "deallocate",
)
_SQL_FORBIDDEN_FUNCS = (
    "sleep",
    "benchmark",
    "load_file",
)


def _strip_sql_comments_and_strings(sql: str) -> str:
    """去除注释与字符串内容，用于安全检查（粗粒度，不追求完美 SQL 解析）。"""
    s = sql or ""
    # 去除 -- 注释与 /* */ 注释
    s = re.sub(r"--.*$", " ", s, flags=re.MULTILINE)
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
    # 去除单引号/双引号字符串
    s = re.sub(r"'([^'\\\\]|\\\\.)*'", "''", s)
    s = re.sub(r"\"([^\"\\\\]|\\\\.)*\"", "\"\"", s)
    return s


def _normalize_sql(sql: str) -> str:
    s = _strip_sql_comments_and_strings(sql)
    return " ".join((s or "").strip().lower().split())


def _ensure_single_statement(sql: str) -> bool:
    # 允许末尾一个分号，但不允许多语句
    s = (sql or "").strip()
    if not s:
        return False
    if s.count(";") == 0:
        return True
    # 只允许最后一个分号
    return s.rstrip().endswith(";") and s.rstrip()[:-1].find(";") == -1


def _sql_is_readonly(sql: str) -> tuple[bool, str]:
    """安全校验：只读前缀 + 禁止关键字/危险函数 + 禁止多语句。"""
    if not _ensure_single_statement(sql):
        return False, "禁止多语句 SQL（仅允许一条只读语句）。"
    s = _normalize_sql(sql)
    if not any(s.startswith(p) for p in _SQL_READONLY_PREFIXES):
        return False, "仅允许只读 SQL（SELECT/SHOW/DESCRIBE/EXPLAIN）。"
    # 禁止关键字（出现在任意位置都拒绝）
    for kw in _SQL_FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", s):
            return False, f"检测到危险关键字 `{kw}`，已拒绝。"
    for fn in _SQL_FORBIDDEN_FUNCS:
        if re.search(rf"\b{re.escape(fn)}\s*\(", s):
            return False, f"检测到危险函数 `{fn}()`，已拒绝。"
    return True, ""


def _maybe_add_limit(sql: str, limit: int = 200) -> str:
    """对 SELECT 查询默认加 LIMIT，避免大结果集拖库；若已含 LIMIT/为聚合 count 则不加。"""
    s = _normalize_sql(sql)
    if not s.startswith("select"):
        return sql
    if re.search(r"\blimit\b", s):
        return sql
    if re.search(r"\bcount\s*\(", s):
        return sql
    return (sql.rstrip().rstrip(";") + f" LIMIT {limit};")


@tool
def execute_readonly_sql(sql: str) -> str:
    """执行只读 SQL（仅允许 SELECT、SHOW、DESCRIBE、EXPLAIN）。禁止 DELETE、UPDATE、INSERT、ALTER 等任何写操作。适用于 ORM 难以表达的复杂查询。"""
    ok, reason = _sql_is_readonly(sql)
    if not ok:
        return reason
    sql = _maybe_add_limit(sql, limit=200)
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.db_host,
            port=int(settings.db_port or 3306),
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
            if not rows:
                return "查询结果为空。"
            return json.dumps(rows, ensure_ascii=False, default=str)
        finally:
            conn.close()
    except ImportError:
        return "未安装 pymysql，无法执行 SQL。请安装: pip install pymysql"
    except Exception as e:
        return f"执行 SQL 出错: {type(e).__name__}: {e}"


@tool
def repair_sql(question: str, sql: str, error: str, schema_hint: str = "") -> str:
    """修复只读 SQL：根据问题、schema_hint 与数据库错误信息，生成修复后的只读 SQL。只允许 SELECT/SHOW/DESCRIBE/EXPLAIN。"""
    client = get_openai_client()
    system = (
        "你是一个 SQL 修复助手。目标：修复用户问题对应的只读 SQL，使其能在给定 schema 下执行成功。\n"
        "严格约束：只输出一条 SQL，且必须是只读（SELECT/SHOW/DESCRIBE/EXPLAIN），禁止任何写操作、禁止多语句、禁止 INTO OUTFILE/LOAD DATA 等危险操作。\n"
        "如果需要引用表/字段，必须来自 schema_hint。"
    )
    payload = {
        "question": question,
        "sql": sql,
        "error": error,
        "schema_hint": schema_hint,
    }
    try:
        completion = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.0,
        )
        fixed = (completion.choices[0].message.content or "").strip()
        # 二次校验，确保修复结果仍只读
        ok, reason = _sql_is_readonly(fixed)
        if not ok:
            return f"修复 SQL 未通过安全校验：{reason}"
        return _maybe_add_limit(fixed, limit=200)
    except Exception as e:
        return f"SQL 修复失败: {type(e).__name__}: {e}"
