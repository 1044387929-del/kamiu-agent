"""
数据库只读工具：Django ORM 内省、ORM 代码执行（只读）、只读 SQL 执行。
供业务查数场景使用；禁止任何写操作。
"""
from __future__ import annotations

import ast
import json
import sys
from typing import Any

from langchain_core.tools import tool

from core.config import settings


def _ensure_django() -> bool:
    """若配置了 Django，将项目路径加入 sys.path 并执行 django.setup()。返回是否成功。"""
    if not (settings.django_settings_module and settings.django_project_path):
        return False
    path = settings.django_project_path.strip()
    if path not in sys.path:
        sys.path.insert(0, path)
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings.django_settings_module)
    try:
        import django
        django.setup()
        return True
    except Exception:
        return False


# 禁止在 ORM 代码中出现的写操作关键字（小写检测）
_ORM_FORBIDDEN = (
    ".delete(", ".update(", ".create(", ".save(", ".bulk_create(",
    ".get_or_create(", ".update_or_create(", ".bulk_update(",
    ".__setattr__", ".__delattr__", "del ", "exec(", "eval(",
    "compile(", "open(", "input(", "subprocess.", "os.system",
)


def _check_orm_readonly(code: str) -> str | None:
    """检查代码是否包含写操作，若有则返回错误说明，否则返回 None。"""
    code_lower = code.lower()
    for token in _ORM_FORBIDDEN:
        if token in code_lower:
            return f"禁止在查询代码中使用写操作或危险调用（检测到: {token.strip('.')}）。仅允许只读查询。"
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr.lower()
                    if name in ("delete", "update", "create", "save", "bulk_create", "get_or_create", "update_or_create", "bulk_update"):
                        return f"禁止调用 .{node.func.attr}()，仅允许只读查询。"
    except SyntaxError:
        pass
    return None


@tool
def get_db_schema(table_prefix: str = "") -> str:
    """获取数据库表结构说明，供生成 Django ORM 查询或 SQL 时参考。建议在生成查询代码前先调用本工具。table_prefix 可选，用于过滤表名（留空则返回所有表）。"""
    if _ensure_django():
        try:
            from django.apps import apps
            from django.db import connection

            parts = []
            for model in apps.get_models():
                table = model._meta.db_table
                if table_prefix and not table.startswith(table_prefix):
                    continue
                fields = []
                for f in model._meta.get_fields():
                    if hasattr(f, "column"):
                        fields.append(f"{f.name} ({f.__class__.__name__})")
                    elif hasattr(f, "related_model") and f.related_model:
                        fields.append(f"{f.name} -> {f.related_model._meta.label}")
                parts.append(f"Model: {model._meta.label}\n  Table: {table}\n  Fields: {', '.join(fields)}")
            return "\n\n".join(parts) if parts else "未找到匹配的模型。"
        except Exception as e:
            return f"Django 内省失败: {e}"
    # 回退：用 INFORMATION_SCHEMA
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
                    "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s ORDER BY TABLE_NAME, ORDINAL_POSITION",
                    (settings.db_name, like),
                )
                rows = cur.fetchall()
            if not rows:
                return "未找到匹配的表。"
            from collections import defaultdict
            by_table = defaultdict(list)
            for r in rows:
                by_table[r["TABLE_NAME"]].append(f"{r['COLUMN_NAME']} ({r['DATA_TYPE']})")
            return "\n".join(f"Table: {t}\n  Columns: {', '.join(cols)}" for t, cols in sorted(by_table.items()))
        finally:
            conn.close()
    except ImportError:
        return "未安装 pymysql；且未配置 Django，无法获取表结构。请配置 DJANGO_SETTINGS_MODULE 与 DJANGO_PROJECT_PATH，或安装 pymysql。"
    except Exception as e:
        return f"从数据库读取表结构失败: {e}"


@tool
def execute_readonly_orm_code(code: str) -> str:
    """执行只读的 Django ORM 代码。代码必须将查询结果赋给变量 result，例如 result = list(Model.objects.filter(...).values())。
    仅允许只读操作（filter、values、annotate 等），禁止 delete、update、create、save。若需复杂统计可改用 execute_readonly_sql。"""
    err = _check_orm_readonly(code)
    if err:
        return err
    if not _ensure_django():
        return "未配置 Django（DJANGO_SETTINGS_MODULE、DJANGO_PROJECT_PATH），无法执行 ORM 代码。"
    try:
        from django.apps import apps
        from django.db.models import Q, F, Count, Sum, Avg, Min, Max, Value
        from django.db.models.functions import Coalesce

        restricted = {
            "result": None,
            "Q": Q,
            "F": F,
            "Count": Count,
            "Sum": Sum,
            "Avg": Avg,
            "Min": Min,
            "Max": Max,
            "Value": Value,
            "Coalesce": Coalesce,
            "list": list,
            "dict": dict,
        }
        for model in apps.get_models():
            restricted[model.__name__] = model
        exec(compile(code, "<orm>", "exec"), restricted)
        out = restricted.get("result")
        if out is None:
            return "代码未将结果赋给变量 result。请确保最后有 result = list(...) 或 result = ..."
        if hasattr(out, "__iter__") and not isinstance(out, (str, bytes)):
            rows = list(out)
            if not rows:
                return "查询结果为空。"
            if hasattr(rows[0], "_asdict"):
                rows = [r._asdict() for r in rows]
            elif hasattr(rows[0], "__dict__"):
                rows = [{k: _serialize(v) for k, v in r.__dict__.items() if not k.startswith("_")} for r in rows]
            elif isinstance(rows[0], dict):
                rows = [{k: _serialize(v) for k, v in r.items()} for r in rows]
            else:
                rows = [str(r) for r in rows]
            return json.dumps(rows, ensure_ascii=False, default=str)
        return str(out)
    except Exception as e:
        return f"执行 ORM 代码出错: {type(e).__name__}: {e}"


def _serialize(v: Any) -> Any:
    from datetime import date, datetime
    from decimal import Decimal
    from uuid import UUID
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, (Decimal, UUID)):
        return str(v)
    if hasattr(v, "pk"):
        return v.pk
    return v


# 只允许的 SQL 语句类型（白名单）
_SQL_READONLY_PREFIXES = ("select", "show", "describe", "desc", "explain")


def _sql_is_readonly(sql: str) -> bool:
    """简单检查：去除注释和空白后，是否以只读关键字开头。"""
    import re
    s = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = s.strip().lower()
    return any(s.startswith(p) for p in _SQL_READONLY_PREFIXES)


@tool
def execute_readonly_sql(sql: str) -> str:
    """执行只读 SQL（仅允许 SELECT、SHOW、DESCRIBE、EXPLAIN）。禁止 DELETE、UPDATE、INSERT、ALTER 等任何写操作。适用于 ORM 难以表达的复杂查询。"""
    if not _sql_is_readonly(sql):
        return "仅允许只读 SQL（SELECT/SHOW/DESCRIBE/EXPLAIN），当前语句被拒绝。"
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
