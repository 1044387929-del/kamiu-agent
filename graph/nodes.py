"""
LangGraph 节点：每个节点接收 state，返回 state 的增量更新。
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage

from core.llm import get_llm, get_openai_client
from core.config import settings
from graph.state import AgentState
from prompts import ASSISTANT_SYSTEM_WITH_TOOLS


def _messages_to_openai(messages: list[BaseMessage]) -> list[dict]:
    """LangChain messages 转 OpenAI API 格式。"""
    out = []
    for m in messages:
        if isinstance(m, SystemMessage):
            out.append({"role": "system", "content": (m.content or "")})
        elif isinstance(m, HumanMessage):
            out.append({"role": "user", "content": (m.content or "")})
        elif isinstance(m, AIMessage):
            out.append({"role": "assistant", "content": (m.content or "")})
    return out


def route_node(state: AgentState) -> AgentState:
    """
    路由节点：根据最后一条用户消息决定下一步（可扩展为调用 LLM 做意图识别）。
    当前为占位：直接进入回复节点。
    """
    return {}


def _agent_node_impl(tools_list: list):
    """返回带工具调用的 agent 节点（LLM 可返回 tool_calls）；支持思考模式时补采 reasoning。"""

    def agent_node(state: AgentState) -> dict:
        messages = state.get("messages") or []
        if not messages:
            return {"messages": [AIMessage(content="你好，我是教师助手。有什么可以帮你的？")]}
        enable_thinking = state.get("enable_thinking", False)
        llm = get_llm()
        if tools_list:
            llm = llm.bind_tools(tools_list)
        full = [SystemMessage(content=ASSISTANT_SYSTEM_WITH_TOOLS)] + list(messages)
        response = llm.invoke(full)
        out = {"messages": [response]}

        # 当用户开启思考模式且本次为最终回复（无 tool_calls）时，用流式请求补采 reasoning
        if enable_thinking and not getattr(response, "tool_calls", None):
            client = get_openai_client()
            openai_messages = _messages_to_openai(full)
            model = settings.llm_model
            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    stream=True,
                    extra_body={"enable_thinking": True},
                    stream_options={"include_usage": True},
                )
                reasoning_parts = []
                for chunk in completion:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if getattr(delta, "reasoning_content", None):
                        reasoning_parts.append(delta.reasoning_content)
                reasoning = "".join(reasoning_parts).strip() or None
                if reasoning:
                    out["last_reasoning"] = reasoning
            except Exception:
                pass
        return out

    return agent_node


def reply_node(state: AgentState) -> AgentState:
    """
    回复节点：调用 LLM 根据当前 messages 生成助手回复。
    """
    messages = state.get("messages") or []
    if not messages:
        return {"messages": [AIMessage(content="你好，我是教师助手。有什么可以帮你的？")]}
    llm = get_llm()
    # 首条为系统提示，便于模型保持角色
    full_messages = [SystemMessage(content=ASSISTANT_SYSTEM_WITH_TOOLS)] + list(messages)
    response = llm.invoke(full_messages)
    content = getattr(response, "content", "") or ""
    return {"messages": [AIMessage(content=content)]}


def inject_system_node(state: AgentState) -> AgentState:
    """
    注入系统提示：在对话前插入角色与权限说明（可选）。
    """
    teacher_id = state.get("teacher_id") or ""
    system = (
        "你是教师智能助手。当前教师 ID：{teacher_id}。"
        "回答要简洁、专业。".format(teacher_id=teacher_id)
    )
    return {"messages": [SystemMessage(content=system)]}
