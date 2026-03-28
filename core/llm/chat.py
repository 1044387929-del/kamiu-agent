"""
对话业务逻辑：组消息、调用 LLM（非流式 / 流式）。
"""
import json
from collections.abc import Generator
from typing import Any

from openai import OpenAI

from core.config import settings
from core.schemas.chat import ChatRequest, ChatResponse
from prompts import ASSISTANT_SYSTEM_TEMPLATE


def build_messages(
    history: list[dict[str, Any]],
    message: str,
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    """将 history + 当前 message 转为 OpenAI 格式的 messages。"""
    if system_prompt is None:
        system_prompt = ASSISTANT_SYSTEM_TEMPLATE.format()
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for i, h in enumerate(history):
        role = "user" if i % 2 == 0 else "assistant"
        content = (h.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return messages


def chat_completion(
    client: OpenAI,
    req: ChatRequest,
) -> ChatResponse:
    """非流式对话：单次请求返回完整 reply（可选 reasoning）。"""
    message = (req.message or "").strip()
    enable_thinking = (
        req.enable_thinking if req.enable_thinking is not None else settings.enable_thinking_default
    )
    model = req.model or settings.llm_model
    messages = build_messages(req.history, message)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if enable_thinking:
        kwargs["stream"] = True
        kwargs["extra_body"] = {"enable_thinking": True}
        kwargs["stream_options"] = {"include_usage": True}
    else:
        kwargs["stream"] = False

    if not enable_thinking:
        completion = client.chat.completions.create(**kwargs)
        content = (completion.choices[0].message.content or "").strip()
        return ChatResponse(reply=content)

    completion = client.chat.completions.create(**kwargs)
    reasoning_content = ""
    answer_content = ""
    for chunk in completion:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if getattr(delta, "reasoning_content", None):
            reasoning_content += delta.reasoning_content
        if getattr(delta, "content", None):
            answer_content += delta.content
    return ChatResponse(
        reply=answer_content.strip(),
        reasoning=reasoning_content.strip() or None,
    )


def chat_completion_stream(
    client: OpenAI,
    req: ChatRequest,
) -> Generator[str, None, None]:
    """流式对话：按 SSE 行 yield。"""
    message = (req.message or "").strip()
    enable_thinking = (
        req.enable_thinking if req.enable_thinking is not None else settings.enable_thinking_default
    )
    model = req.model or settings.llm_model
    messages = build_messages(req.history, message)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if enable_thinking:
        kwargs["extra_body"] = {"enable_thinking": True}

    completion = client.chat.completions.create(**kwargs)
    for chunk in completion:
        if not chunk.choices:
            if hasattr(chunk, "usage") and chunk.usage:
                yield f"data: {json.dumps({'type': 'usage', 'usage': chunk.usage.model_dump()}, ensure_ascii=False)}\n\n"
            continue
        delta = chunk.choices[0].delta
        if enable_thinking and getattr(delta, "reasoning_content", None):
            yield f"data: {json.dumps({'type': 'reasoning', 'content': delta.reasoning_content}, ensure_ascii=False)}\n\n"
        if getattr(delta, "content", None):
            yield f"data: {json.dumps({'type': 'content', 'content': delta.content}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
