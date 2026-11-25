from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.routers.documents import ask_load_chunks
from app.services import ollama

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    pergunta: str = Field(min_length=3)
    estado: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    pesquisar_web: bool = False


@router.post("/ask")
def ask(req: AskRequest):
    chunks = ask_load_chunks(req.estado)
    relevant = ollama.retrieve(req.pergunta, chunks, top_k=req.top_k) if chunks else []

    context = "\n\n---\n\n".join(
        f"[Fonte: {c['original_name']} | Estado: {c['estado']} | "
        f"Disciplina: {c.get('disciplina') or '-'} | Assunto: {c.get('assunto') or '-'}]\n{c['content']}"
        for c in relevant
    )

    web_sources = []
    if req.pesquisar_web:
        try:
            from app.research import retriever, search_engine

            results = search_engine.search(
                req.pergunta, estado=req.estado, max_results=req.top_k
            )
            web_sources = [r.model_dump() for r in results]
            web_chunks = retriever.web_results_to_chunks(results)
            web_context = "\n\n---\n\n".join(
                f"[Fonte web: {c['original_name']}]\n{c['content']}" for c in web_chunks
            )
            if web_context:
                context = (context + "\n\n" if context else "") + "FONTES WEB:\n" + web_context
        except Exception:
            pass

    answer = None
    if context:
        answer = ollama.ask_ollama(req.pergunta, context)

    return {
        "pergunta": req.pergunta,
        "fontes_usadas": len(relevant),
        "fontes_web": len(web_sources),
        "fontes_web_detalhes": web_sources[:5],
        "ia_disponivel": ollama.is_ollama_available(),
        "resposta": answer,
        "contexto": context if not answer else None,
        "aviso": None
        if answer
        else "Modelo de IA indisponível ou sem contexto suficiente. Contexto recuperado retornado para inspeção.",
    }


@router.get("/status")
def status():
    return {
        "ollama_disponivel": ollama.is_ollama_available(),
        "modelo": ollama.OLLAMA_MODEL,
    }
