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
from core.llm import get_openai_client
from graph.graph import get_graph


def _select_history_indices_by_rounds(
    history_len: int,
    keep_start_rounds: int,
    keep_end_rounds: int,
) -> tuple[list[int], list[int]]:
    """
    选择 history 的保留/丢弃下标（按轮次：每轮 2 条 user/assistant）。

    - 保留：开头 keep_start_rounds 轮 + 末尾 keep_end_rounds 轮
    - 丢弃：中间剩余

    返回的是“原始下标集合”，后续构建消息时可按原始下标奇偶确定角色，
    避免因切片导致的 user/assistant 角色错位。
    """
    if history_len <= 0 or (keep_start_rounds <= 0 and keep_end_rounds <= 0):
        return list(range(history_len)), []

    total_rounds = (history_len + 1) // 2
    if total_rounds <= 0:
        return list(range(history_len)), []
    if keep_start_rounds + keep_end_rounds >= total_rounds:
        return list(range(history_len)), []

    start_count = min(keep_start_rounds, total_rounds) * 2
    end_count = min(keep_end_rounds, total_rounds) * 2
    if start_count + end_count >= history_len:
        return list(range(history_len)), []

    keep_indices = list(range(0, start_count)) + list(range(history_len - end_count, history_len))
    keep_set = set(keep_indices)
    dropped_indices = [i for i in range(history_len) if i not in keep_set]
    return keep_indices, dropped_indices


def _parse_json_array_or_object(raw: str) -> object | None:
    """
    兼容模型输出中可能存在的 markdown 代码块/前后噪声。
    返回解析后的 JSON 对象（dict/list），解析失败返回 None。
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if "```" in text:
        start = text.find("```")
        rest = text[start + 3 :].strip()
        if rest.lower().startswith("json"):
            rest = rest[4:].strip()
        end = rest.find("```")
        text = rest[:end].strip() if end >= 0 else rest
    try:
        return json.loads(text)
    except Exception:
        return None


def _build_dropped_transcript(history: list[dict], dropped_indices: list[int], max_chars: int) -> str:
    """把丢弃的历史片段拼成“可用于摘要提取”的短文本。"""
    if not dropped_indices:
        return ""
    lines: list[str] = []
    for i in dropped_indices:
        h = history[i] if i < len(history) else {}
        content = (h.get("content") or "").strip()
        if not content:
            continue
        role = "用户" if i % 2 == 0 else "助手"
        lines.append(f"{role}：{content}")
    transcript = "\n".join(lines).strip()
    if max_chars > 0 and len(transcript) > max_chars:
        # 优先保留尾部（更接近当前）
        transcript = transcript[-max_chars:]
    return transcript


def _extract_memory_summary_and_facts(dropped_transcript: str) -> tuple[str | None, list[str] | None]:
    """用 LLM 从被丢弃的旧内容中提取会话摘要与关键事实。"""
    if not settings.memory_summary_enabled:
        return None, None
    if not dropped_transcript or not dropped_transcript.strip():
        return None, None

    if len(dropped_transcript) < settings.memory_summary_min_dropped_chars:
        return None, None

    # 额外摘要提取的输入也做长度控制，避免无意义 token 消耗
    input_text = dropped_transcript[: settings.memory_summary_max_dropped_chars].strip()
    if not input_text:
        return None, None

    model = settings.memory_summary_model or settings.llm_model
    client = get_openai_client()

    system = (
        "你是会话记忆提取器。"
        "目标是从“被截断丢弃的旧对话内容”中抽取："
        "1) 一个简短会话摘要（不超过 6 句，保留明确约束/目标/结论/未解决事项）；"
        "2) 若干关键事实列表（每条一句话，尽量用可复用的陈述句）。"
        "要求：只基于输入中明确出现的信息，不要编造。"
        "输出严格为 JSON 对象："
        "{\"summary\": \"...\", \"key_facts\": [\"...\", \"...\"]}。"
        "不要输出 markdown，不要输出额外字段。"
    )
    user = (
        "以下是历史对话中“被截断丢弃”的旧内容（供提取记忆）：\n\n"
        f"{input_text}\n\n"
        f"关键事实最多 {settings.memory_key_facts_max} 条。摘要最多 {settings.memory_summary_max_chars} 字符。"
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        max_tokens=settings.memory_summary_max_tokens,
    )
    raw = getattr(completion.choices[0].message, "content", "") if completion and completion.choices else ""
    parsed = _parse_json_array_or_object(raw)
    if not isinstance(parsed, dict):
        return None, None

    summary = (parsed.get("summary") or "").strip() or None
    if summary:
        summary = summary[: settings.memory_summary_max_chars]

    key_facts = parsed.get("key_facts") or []
    if not isinstance(key_facts, list):
        key_facts = []
    key_facts = [str(x).strip() for x in key_facts if str(x).strip()]
    if settings.memory_key_facts_max > 0:
        key_facts = key_facts[: settings.memory_key_facts_max]
    return summary, key_facts


def chat_request_to_messages_and_memory(req: ChatRequest) -> tuple[list, str | None, list[str] | None]:
    """
    将 ChatRequest 转为 LangChain messages，并在必要时构造会话记忆：
    当 history 因轮次截断发生“中间丢弃”时，对丢弃内容进行摘要/关键事实提取，并注入系统提示。
    """
    history = req.history or []
    keep_indices, dropped_indices = _select_history_indices_by_rounds(
        len(history),
        settings.chat_keep_start_rounds,
        settings.chat_keep_end_rounds,
    )

    messages: list = []
    for i in keep_indices:
        h = history[i] if i < len(history) else {}
        content = (h.get("content") or "").strip()
        if not content:
            continue
        if i % 2 == 0:
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    # 当前用户消息
    current = (req.message or "").strip()
    messages.append(HumanMessage(content=current))
    if not current:
        return [], None, None

    # 允许上游直接传入 memory，避免重复摘要提取
    if (req.memory_summary or "").strip():
        summary = (req.memory_summary or "").strip()[: settings.memory_summary_max_chars]
        key_facts = req.key_facts or []
        if isinstance(key_facts, list):
            key_facts = [str(x).strip() for x in key_facts if str(x).strip()][: settings.memory_key_facts_max]
        else:
            key_facts = None
        return messages, summary, key_facts

    dropped_transcript = _build_dropped_transcript(
        history=history,
        dropped_indices=dropped_indices,
        max_chars=settings.memory_summary_max_dropped_chars,
    )
    if not dropped_transcript or len(dropped_transcript) < settings.memory_summary_min_dropped_chars:
        return messages, None, None

    summary, key_facts = _extract_memory_summary_and_facts(dropped_transcript)
    return messages, summary, key_facts


def chat_with_agent(req: ChatRequest) -> ChatResponse:
    """走图执行对话（含工具），返回最终回复；若开启思考模式则带 reasoning。"""
    messages, memory_summary, key_facts = chat_request_to_messages_and_memory(req)
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
    config = {"recursion_limit": 25}
    result = graph.invoke({
        "messages": messages,
        "enable_thinking": enable_thinking,
        "enable_web_search": enable_web_search,
        "model": model,
        "memory_summary": memory_summary,
        "key_facts": key_facts,
    }, config=config)
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
    messages, memory_summary, key_facts = chat_request_to_messages_and_memory(req)
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
        "memory_summary": memory_summary,
        "key_facts": key_facts,
    }
    graph = get_graph(enable_web_search=enable_web_search)
    result_holder = []

    config = {"recursion_limit": 25}

    def run_graph():
        try:
            result = graph.invoke(initial_state, config=config)
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