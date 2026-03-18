"""
LangGraph 图构建：定义节点与边，返回可 invoke/stream 的图。
支持按 enable_web_search 动态注入工具：先尝试非联网工具，解决不了再可联网搜索。
"""
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

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
    """构建并编译图。enable_web_search 为 True 时注入 web_search 工具；agent 优先用非联网工具，解决不了再联网。"""
    tools_list = get_tools_list(enable_web_search)
    builder = StateGraph(AgentState)
    tool_node = ToolNode(tools_list)

    builder.add_node("route", route_node)
    builder.add_node("agent", _agent_node_impl(tools_list))
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "route")
    builder.add_edge("route", "agent")
    builder.add_conditional_edges("agent", _has_tool_calls, {"tools": "tools", "end": END})
    builder.add_edge("tools", "agent")

    return builder.compile()
