from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import settings
from core.embeddings import embed_texts


@dataclass(frozen=True)
class SchemaDoc:
    table: str
    content: str


def _meta_path() -> Path:
    return Path(settings.chroma_persist_dir) / "_schema_meta.json"


def _fingerprint(text: str) -> str:
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()[:16]


def _ensure_dir() -> None:
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)


def _get_collection_name(db_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in (db_name or "default"))
    return f"schema_summary__{safe}"


def _load_meta() -> dict[str, Any]:
    p = _meta_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_meta(meta: dict[str, Any]) -> None:
    p = _meta_path()
    _ensure_dir()
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_table_name(block: str) -> str:
    # block header format: "Table: xxx  # comment"
    first = (block or "").strip().splitlines()[0] if (block or "").strip() else ""
    if first.lower().startswith("table:"):
        rest = first.split(":", 1)[1].strip()
        return rest.split("#", 1)[0].strip() or "unknown"
    return "unknown"


def schema_docs_from_blocks(blocks: list[str]) -> list[SchemaDoc]:
    docs: list[SchemaDoc] = []
    for b in blocks:
        bb = (b or "").strip()
        if not bb:
            continue
        docs.append(SchemaDoc(table=_parse_table_name(bb), content=bb))
    return docs


def upsert_schema_blocks(full_schema_text: str, blocks: list[str]) -> None:
    """Build/update schema summary vector index (local Chroma)."""
    try:
        import chromadb  # type: ignore
    except Exception:
        return

    _ensure_dir()
    fp = _fingerprint(full_schema_text)
    db_name = settings.db_name or "default"
    collection_name = _get_collection_name(db_name)

    meta = _load_meta()
    if meta.get("db_name") == db_name and meta.get("fingerprint") == fp and meta.get("collection") == collection_name:
        return

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    col = client.get_or_create_collection(collection_name, metadata={"db_name": db_name, "fingerprint": fp})

    docs = schema_docs_from_blocks(blocks)
    if not docs:
        _save_meta({"db_name": db_name, "fingerprint": fp, "collection": collection_name, "count": 0})
        return

    embeddings = embed_texts([d.content for d in docs])
    ids = [f"{d.table}__{i}" for i, d in enumerate(docs)]
    metadatas = [{"table": d.table} for d in docs]
    col.add(ids=ids, documents=[d.content for d in docs], embeddings=embeddings, metadatas=metadatas)

    _save_meta({"db_name": db_name, "fingerprint": fp, "collection": collection_name, "count": len(docs)})


def retrieve_schema_blocks(query: str, top_k: int = 12) -> list[str]:
    """Vector-retrieve relevant schema blocks. Returns empty list if unavailable."""
    try:
        import chromadb  # type: ignore
    except Exception:
        return []

    q = (query or "").strip()
    if not q:
        return []
    _ensure_dir()
    db_name = settings.db_name or "default"
    collection_name = _get_collection_name(db_name)
    meta = _load_meta()
    if meta.get("db_name") != db_name or meta.get("collection") != collection_name or not meta.get("count"):
        return []

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    col = client.get_or_create_collection(collection_name)
    q_emb = embed_texts([q])[0]
    res = col.query(query_embeddings=[q_emb], n_results=max(1, int(top_k)))
    docs = (res.get("documents") or [[]])[0] or []
    return [d for d in docs if isinstance(d, str) and d.strip()]

