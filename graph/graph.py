"""
LangGraph 图构建：定义节点与边，返回可 invoke/stream 的图。
"""
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from graph.state import AgentState
from graph.nodes import reply_node, route_node

# 若有工具，可在此注册；暂无则用占位流程
# from tools.xxx import tools_list
# tool_node = ToolNode(tools_list)


def get_graph():
    """构建并编译图，返回 CompiledGraph。"""
    builder = StateGraph(AgentState)

    # 节点
    builder.add_node("route", route_node)
    builder.add_node("reply", reply_node)
    # 若有工具： builder.add_node("tools", tool_node)

    # 边：START -> route -> reply -> END
    builder.add_edge(START, "route")
    builder.add_edge("route", "reply")
    builder.add_edge("reply", END)

    return builder.compile()
