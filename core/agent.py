"""
基于 LangGraph 的对话：带工具调用（如 get_current_time），支持思考模式返回 reasoning。
流式 / 非流式都走同一套 Agent 图；流式时 agent 节点边生成边推送到 queue，实现边生成边返回。
"""
import json
import queue
import threading
from collections.abc import Generator

from langchain_core.messages import AIMessage, HumanMessage

from core.config import settings
from core.dashscope_models import is_valid_model
from core.schemas.chat import ChatRequest, ChatResponse
from graph.graph import get_graph


def chat_request_to_messages(req: ChatRequest) -> list:
    """将 ChatRequest 转为 LangChain messages（HumanMessage / AIMessage）。"""
    messages = []
    history = req.history or []
    for i, h in enumerate(history):
        content = (h.get("content") or "").strip()
        if not content:
            continue
        if i % 2 == 0:
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=(req.message or "").strip()))
    return messages


def chat_with_agent(req: ChatRequest) -> ChatResponse:
    """走图执行对话（含工具），返回最终回复；若开启思考模式则带 reasoning。"""
    messages = chat_request_to_messages(req)
    if not messages:
        return ChatResponse(reply="你好，我是教师助手。有什么可以帮你的？")
    enable_thinking = (
        req.enable_thinking if req.enable_thinking is not None else settings.enable_thinking_default
    )
    enable_web_search = req.enable_web_search
    model = (req.model or "").strip() or None
    if model and not is_valid_model(model):
        model = None
    if not model:
        model = settings.llm_model
    graph = get_graph(enable_web_search=enable_web_search)
    result = graph.invoke({
        "messages": messages,
        "enable_thinking": enable_thinking,
        "enable_web_search": enable_web_search,
        "model": model,
    })
    final_messages = result.get("messages") or []
    reply = ""
    for m in reversed(final_messages):
        if hasattr(m, "content") and getattr(m, "content", None):
            reply = (m.content or "").strip()
            break
    reasoning = result.get("last_reasoning")
    return ChatResponse(reply=reply or "抱歉，没有生成回复。", reasoning=reasoning)


def _sse_event(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def chat_with_agent_stream(req: ChatRequest) -> Generator[str, None, None]:
    """走图执行对话（含工具），agent 节点内用 llm.stream() 边生成边推送到 queue，本函数从 queue 读出并 yield SSE。"""
    messages = chat_request_to_messages(req)
    if not messages:
        yield _sse_event({"type": "content", "content": "你好，我是教师助手。有什么可以帮你的？"})
        yield _sse_event({"type": "done"})
        return
    enable_thinking = (
        req.enable_thinking if req.enable_thinking is not None else settings.enable_thinking_default
    )
    enable_web_search = req.enable_web_search
    model = (req.model or "").strip() or None
    if model and not is_valid_model(model):
        model = None
    if not model:
        model = settings.llm_model
    stream_queue = queue.Queue()
    initial_state = {
        "messages": messages,
        "enable_thinking": enable_thinking,
        "enable_web_search": enable_web_search,
        "model": model,
        "stream_queue": stream_queue,
    }
    graph = get_graph(enable_web_search=enable_web_search)
    result_holder = []

    def run_graph():
        try:
            result = graph.invoke(initial_state)
            result_holder.append(result)
            if result.get("last_reasoning"):
                stream_queue.put(("reasoning", result["last_reasoning"]))
        except Exception as e:
            stream_queue.put(("content", f"请求出错：{e}"))
        finally:
            stream_queue.put(("done",))

    thread = threading.Thread(target=run_graph)
    thread.start()
    while True:
        item = stream_queue.get()
        if item[0] == "done":
            break
        if item[0] == "reasoning":
            yield _sse_event({"type": "reasoning", "content": item[1]})
        elif item[0] == "content":
            yield _sse_event({"type": "content", "content": item[1]})
        elif item[0] == "exec":
            yield _sse_event({"type": "exec", **(item[1] or {})})
        elif item[0] == "exec_result":
            yield _sse_event({"type": "exec_result", **(item[1] or {})})
    yield _sse_event({"type": "done"})