import json
import math
import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
EMBEDDINGS_ENABLED = os.environ.get("EMBEDDINGS_ENABLED", "true").lower() == "true"

_embed_model_ok: bool | None = None


def embed_model_available() -> bool:
    global _embed_model_ok
    if _embed_model_ok is not None:
        return _embed_model_ok
    if not EMBEDDINGS_ENABLED:
        _embed_model_ok = False
        return False
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0)
        models = [m["name"] for m in r.json().get("models", [])]
        _embed_model_ok = any(EMBED_MODEL in m for m in models)
    except Exception:
        _embed_model_ok = False
    return _embed_model_ok


def embed_text(text: str) -> list[float] | None:
    if not embed_model_available():
        return None
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text[:8000]},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json().get("embedding")
    except Exception:
        return None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embed_chunks_sync(conn, doc_id: int) -> int:
    """Gera embeddings para chunks de um documento. Retorna quantos foram gerados."""
    if not embed_model_available():
        return 0
    rows = conn.execute(
        "SELECT id, content FROM chunks WHERE document_id = ? AND embedding IS NULL",
        (doc_id,),
    ).fetchall()
    count = 0
    for row in rows:
        vec = embed_text(row["content"])
        if vec:
            conn.execute(
                "UPDATE chunks SET embedding = ? WHERE id = ?",
                (json.dumps(vec), row["id"]),
            )
            count += 1
    return count
