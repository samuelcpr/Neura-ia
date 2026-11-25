import json
import os
import re

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

STOPWORDS = set(
    "a o e de da do das dos em um uma para por com que não na no nas nos "
    "é são foi ser ter seu sua seus suas como mais ao aos à às este esta "
    "isso esse essa entre sobre até também já ou se".split()
)


def tokenize(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-záàâãéêíóôõúç]{3,}", text.lower())
        if t not in STOPWORDS
    ]


def score_chunk(query_tokens: list[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    content_tokens = tokenize(content)
    if not content_tokens:
        return 0.0
    counts = {}
    for t in content_tokens:
        counts[t] = counts.get(t, 0) + 1
    score = 0.0
    for t in query_tokens:
        score += counts.get(t, 0)
    return score / len(query_tokens)


def retrieve(question: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    from app.services import embeddings

    query_tokens = tokenize(question)
    query_vec = embeddings.embed_text(question)

    scored = []
    for c in chunks:
        kw = score_chunk(query_tokens, c["content"])
        score = kw
        if query_vec:
            score = kw * 0.3  # chunks sem embedding ficam em desvantagem
            if c.get("embedding"):
                try:
                    vec = json.loads(c["embedding"]) if isinstance(c["embedding"], str) else c["embedding"]
                    score = embeddings.cosine(query_vec, vec)
                except Exception:
                    pass
        scored.append({**c, "score": round(score, 4)})

    scored.sort(key=lambda c: c["score"], reverse=True)
    min_score = 0.15 if query_vec else 0.0
    return [c for c in scored[:top_k] if c["score"] > min_score]


def generate_raw(prompt: str, json_mode: bool = False, timeout: float = 300.0) -> str | None:
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    if json_mode:
        payload["format"] = "json"
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception:
        return None


def generate_json(prompt: str) -> dict | None:
    raw = generate_raw(prompt, json_mode=True)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # tenta extrair o primeiro objeto JSON
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def is_ollama_available() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def ask_ollama(question: str, context: str) -> str | None:
    prompt = (
        "Você é a NeuralJuris AI, assistente de estudos para concursos públicos "
        "de Goiás, Tocantins e Bahia. Responda em português, de forma objetiva "
        "e didática. Use apenas o contexto fornecido quando ele for relevante; "
        "nunca invente artigos de lei, súmulas ou precedentes.\n\n"
        f"CONTEXTO:\n{context}\n\nPERGUNTA: {question}\n\nRESPOSTA:"
    )
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=300.0,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception:
        return None
