"""
LangGraph 图构建：定义节点与边，返回可 invoke/stream 的图。
"""
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from graph.state import AgentState
from graph.nodes import route_node, _agent_node_impl
from tools import tools_list


def _has_tool_calls(state: AgentState) -> str:
    """若最后一条消息有 tool_calls 则走 tools，否则结束。"""
    messages = state.get("messages") or []
    if not messages:
        return "end"
    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "end"


def get_graph():
    """构建并编译图，返回 CompiledGraph。agent 可调用工具，工具结果后回到 agent。"""
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
