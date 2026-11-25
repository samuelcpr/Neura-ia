"""RAG Engine — orquestra recuperação e geração de respostas fundamentadas."""
import json

from app.services import ollama

from . import retriever, search_engine
from .schemas import SourceResult


def build_context(local_chunks: list[dict], web_chunks: list[dict], max_chunks: int = 10) -> str:
    """Monta contexto combinado priorizando chunks locais."""
    all_chunks = []
    for c in local_chunks[:5]:
        all_chunks.append({
            "content": c.get("content", ""),
            "source": c.get("original_name", "documento local"),
            "type": "local",
        })
    for c in web_chunks[:5]:
        all_chunks.append({
            "content": c.get("content", ""),
            "source": c.get("original_name", "fonte web"),
            "type": "web",
        })

    context_parts = []
    for i, chunk in enumerate(all_chunks[:max_chunks], 1):
        context_parts.append(f"[{i}] {chunk['source']}\n{chunk['content']}")
    return "\n\n---\n\n".join(context_parts)


def generate_answer(question: str, context: str, estado: str | None = None) -> str | None:
    """Gera resposta fundamentada usando Ollama."""
    if not context:
        return None

    prompt = f"""Você é a NeuralJuris AI, especialista em concursos públicos de Goiás, Tocantins e Bahia.

INSTRUÇÕES:
- Responda em português de forma clara e objetiva
- Use APENAS o contexto fornecido
- Cite as fontes quando usar informações do contexto
- Se o contexto não contiver a resposta, diga explicitamente
- Nunca invente artigos de lei, súmulas ou jurisprudência
- Priorize precisão sobre completude

CONTEXTO:
{context}

PERGUNTA: {question}

RESPOSTA:"""

    try:
        response = ollama.ask_ollama(question, context)
        return response
    except Exception:
        return None


def hybrid_search(query: str, estado: str | None = None, top_k: int = 5) -> dict:
    """Busca híbrida: base local + web."""
    # busca local
    local = retriever.local_chunks(estado, query, top_k=top_k)

    # busca web
    web_results = search_engine.search(query, estado=estado, max_results=top_k)
    web_chunks = retriever.web_results_to_chunks(web_results)

    return {
        "local": local,
        "web": web_chunks,
        "web_results": web_results,
    }
