from __future__ import annotations

from typing import Sequence

from core.config import settings
from core.llm import get_openai_client


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed texts using DashScope-compatible OpenAI embeddings API."""
    client = get_openai_client()
    inputs = [t if isinstance(t, str) else str(t) for t in texts]
    resp = client.embeddings.create(
        model=settings.embedding_model,
        input=inputs,
    )
    return [d.embedding for d in resp.data]

