"""
LangGraph 图构建：定义节点与边，返回可 invoke/stream 的图。
支持按 enable_web_search 动态注入工具：先尝试非联网工具，解决不了再可联网搜索。
"""
from langgraph.graph import END, START, StateGraph
from langchain_core.messages import ToolMessage

from graph.state import AgentState
from graph.nodes import route_node, _agent_node_impl
from graph.schema_link import schema_link_node
from tools import get_tools_list


def _has_tool_calls(state: AgentState) -> str:
    """若最后一条消息有 tool_calls 则走 tools，否则结束。"""
    messages = state.get("messages") or []
    if not messages:
        return "end"
    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "end"


def get_graph(enable_web_search: bool = False):
    """构建并编译图。

    - ToolNode 注入“全量工具”（含 DB/联网），以便当 agent 发起 tool_calls 时可执行。
    - agent 节点会根据 state 动态 bind 工具（路由 + 用户开关），实现按 query 选择外挂工具。
    """
    tools_list = get_tools_list(enable_web_search=True, enable_db_query=True)
    builder = StateGraph(AgentState)

    tools_by_name = {t.name: t for t in tools_list}

    def tools_node(state: AgentState) -> dict:
        """执行 tool_calls，并在流式模式下推送 exec/exec_result 事件。"""
        messages = state.get("messages") or []
        if not messages:
            return {}
        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        if not tool_calls:
            return {}

        stream_queue = state.get("stream_queue")
        question = ""
        for m in reversed(messages):
            if hasattr(m, "type") and getattr(m, "type", None) == "human":
                question = (getattr(m, "content", "") or "").strip()
                break
        schema_hint = (state.get("schema_link") or "").strip()
        out_messages = []
        for call in tool_calls:
            # 兼容 LangChain ToolCall 对象 / dict
            name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
            args = getattr(call, "args", None) or (call.get("args") if isinstance(call, dict) else None) or {}
            call_id = getattr(call, "id", None) or (call.get("id") if isinstance(call, dict) else None) or ""

            tool = tools_by_name.get(name or "")
            if tool is None:
                content = f"未知工具：{name}"
                out_messages.append(ToolMessage(content=content, tool_call_id=call_id))
                continue

            def _push_exec(attempt: int, lang: str, code_text: str):
                if stream_queue is None:
                    return
                stream_queue.put(
                    (
                        "exec",
                        {
                            "id": f"{call_id}:{attempt}",
                            "tool": name,
                            "lang": lang,
                            "code": code_text,
                            "attempt": attempt,
                        },
                    )
                )

            def _push_result(attempt: int, result_text: str):
                if stream_queue is None:
                    return
                stream_queue.put(
                    (
                        "exec_result",
                        {
                            "id": f"{call_id}:{attempt}",
                            "tool": name,
                            "result": result_text,
                            "attempt": attempt,
                        },
                    )
                )

            # DB 执行（SQL）：失败自动修复并重试
            if name == "execute_readonly_sql":
                max_attempts = 3
                attempt = 1
                current_args = dict(args)
                while True:
                    sql = (current_args.get("sql") or "").strip()
                    _push_exec(attempt, "sql", sql)

                    try:
                        result = tool.invoke(current_args)
                    except Exception as e:
                        result = f"工具执行出错：{type(e).__name__}: {e}"

                    _push_result(attempt, str(result))

                    result_str = str(result)
                    is_error = (
                        result_str.startswith("执行 SQL 出错:")
                        or result_str.startswith("仅允许只读 SQL")
                        or result_str.startswith("禁止多语句 SQL")
                        or result_str.startswith("检测到危险关键字")
                        or result_str.startswith("检测到危险函数")
                    )
                    if (not is_error) or attempt >= max_attempts:
                        out_messages.append(ToolMessage(content=result_str, tool_call_id=call_id))
                        break

                    # 尝试修复：调用 repair 工具生成新语句
                    attempt += 1
                    repair_tool = tools_by_name.get("repair_sql")
                    if not repair_tool:
                        out_messages.append(ToolMessage(content=result_str, tool_call_id=call_id))
                        break
                    fixed = repair_tool.invoke(
                        {
                            "question": question,
                            "sql": (current_args.get("sql") or ""),
                            "error": result_str,
                            "schema_hint": schema_hint,
                        }
                    )
                    current_args["sql"] = str(fixed)
            else:
                # 非 DB 工具：一次执行
                try:
                    result = tool.invoke(args)
                except Exception as e:
                    result = f"工具执行出错：{type(e).__name__}: {e}"
                out_messages.append(ToolMessage(content=str(result), tool_call_id=call_id))

        return {"messages": out_messages}

    builder.add_node("route", route_node)
    builder.add_node("schema_link", schema_link_node)
    builder.add_node("agent", _agent_node_impl())
    builder.add_node("tools", tools_node)

    builder.add_edge(START, "route")
    # 若 route 判定需要查库，则先做 schema linking 再进入 agent，否则直接进 agent
    def _need_schema_link(state: AgentState) -> str:
        return "schema_link" if state.get("enable_db_query") else "agent"

    builder.add_conditional_edges("route", _need_schema_link, {"schema_link": "schema_link", "agent": "agent"})
    builder.add_edge("schema_link", "agent")
    builder.add_conditional_edges("agent", _has_tool_calls, {"tools": "tools", "end": END})
    builder.add_edge("tools", "agent")

    # recursion_limit 在 invoke 时通过 config 传入，compile 不再支持该参数
    return builder.compile()
