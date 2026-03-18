"""
LangGraph 图构建：定义节点与边，返回可 invoke/stream 的图。
支持按 enable_web_search 动态注入工具：先尝试非联网工具，解决不了再可联网搜索。
"""
from langgraph.graph import END, START, StateGraph
from langchain_core.messages import ToolMessage

from graph.state import AgentState
from graph.nodes import route_node, _agent_node_impl
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

            # 执行前：若是 ORM/SQL，先把“将要执行的代码”推到前端
            if stream_queue is not None and name in ("execute_readonly_orm_code", "execute_readonly_sql"):
                if name == "execute_readonly_orm_code":
                    code = (args.get("code") or "").strip()
                    stream_queue.put(
                        (
                            "exec",
                            {"id": call_id, "tool": name, "lang": "python", "code": code},
                        )
                    )
                else:
                    sql = (args.get("sql") or "").strip()
                    stream_queue.put(
                        (
                            "exec",
                            {"id": call_id, "tool": name, "lang": "sql", "code": sql},
                        )
                    )

            try:
                result = tool.invoke(args)
            except Exception as e:
                result = f"工具执行出错：{type(e).__name__}: {e}"

            # 执行后：推送结果（前端将覆盖掉之前的代码块显示）
            if stream_queue is not None and name in ("execute_readonly_orm_code", "execute_readonly_sql"):
                stream_queue.put(
                    (
                        "exec_result",
                        {"id": call_id, "tool": name, "result": result},
                    )
                )

            out_messages.append(ToolMessage(content=str(result), tool_call_id=call_id))

        return {"messages": out_messages}

    builder.add_node("route", route_node)
    builder.add_node("agent", _agent_node_impl())
    builder.add_node("tools", tools_node)

    builder.add_edge(START, "route")
    builder.add_edge("route", "agent")
    builder.add_conditional_edges("agent", _has_tool_calls, {"tools": "tools", "end": END})
    builder.add_edge("tools", "agent")

    return builder.compile()
