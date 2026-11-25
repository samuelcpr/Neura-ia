"""Research Service — orquestra pesquisa, extração, indexação e resposta fundamentada."""
import json
import time
from datetime import datetime, timezone

from app import db
from app.services import ollama

from . import crawler, retriever, search_engine
from .citation_manager import build_references, is_safe_url
from .document_processor import clean_text, detect_metadata
from .schemas import ResearchAnalyzeRequest, ResearchSearchRequest, SourceResult
from .sources import FONTES_OFICIAIS


def _log_research(conn, query: str, estado: str | None, results: list, answer: str | None):
    conn.execute(
        """INSERT INTO research_log (query, estado, resultados, resposta, created_at)
           VALUES (?,?,?,?,?)""",
        (query, estado, json.dumps([r.model_dump() for r in results], ensure_ascii=False),
         answer, datetime.now(timezone.utc).isoformat()),
    )


def search(req: ResearchSearchRequest) -> dict:
    results = search_engine.search(
        req.query, estado=req.estado, fontes=req.fontes, max_results=req.max_resultados
    )
    return {
        "query": req.query,
        "total": len(results),
        "resultados": [r.model_dump() for r in results],
        "fontes_disponiveis": list(FONTES_OFICIAIS.keys()),
    }


def analyze(req: ResearchAnalyzeRequest) -> dict:
    """Pesquisa profunda: busca fontes, extrai conteúdo, indexa e responde com citações."""
    started = time.time()

    # 1. Busca web/fontes oficiais
    web_results = search_engine.search(
        req.pergunta, estado=req.estado, fontes=req.fontes, max_results=req.max_fontes
    )

    # 2. Recupera base local
    local = retriever.local_chunks(req.estado, req.pergunta, top_k=5)

    # 3. Converte resultados web em chunks de contexto
    web_chunks = retriever.web_results_to_chunks(web_results[:req.max_fontes])

    # 4. Monta contexto combinado (local + web)
    all_context = []
    for c in local + web_chunks:
        all_context.append(
            f"[Fonte: {c.get('original_name','?')} | {c.get('estado','?')}]\n{c['content']}"
        )
    context = "\n\n---\n\n".join(all_context[:10])

    # 5. Gera resposta com Ollama
    answer = None
    if context:
        answer = ollama.ask_ollama(req.pergunta, context)

    # 6. Referências
    refs = build_references([r for r in web_results if is_safe_url(r.url)])

    # 7. Log
    with db.get_conn() as conn:
        _log_research(conn, req.pergunta, req.estado, web_results, answer)

    return {
        "pergunta": req.pergunta,
        "estado": req.estado,
        "fontes_web": len(web_results),
        "fontes_locais": len(local),
        "resposta": answer,
        "referencias": refs,
        "resultados": [r.model_dump() for r in web_results],
        "tempo_segundos": round(time.time() - started, 2),
    }


def crawl_and_index(url: str, estado: str = "FEDERAL", max_chars: int = 15000) -> dict:
    """Faz crawl de uma URL, extrai texto e indexa na base de conhecimento."""
    try:
        status, content, ctype = crawler.fetch(url)
    except Exception as e:
        return {"url": url, "erro": str(e)}

    text = ""
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        from .document_processor import extract_pdf_from_bytes
        from pathlib import Path
        tmp = Path(db.UPLOAD_DIR) / "tmp_crawl.pdf"
        try:
            text = extract_pdf_from_bytes(content, tmp)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        html = content.decode("utf-8", errors="replace")
        text = crawler.html_to_text(html, max_chars=max_chars)

    text = clean_text(text)
    if not text:
        return {"url": url, "erro": "Nenhum texto extraído"}

    meta = detect_metadata(text, url)
    result = SourceResult(
        titulo=meta["titulo"] or url,
        url=url,
        fonte="crawl",
        trecho=text[:12000],
        data=meta["data"],
        tipo="web",
    )
    doc_id = retriever.index_web_document(result, estado=estado)
    return {"url": url, "document_id": doc_id, "chars": len(text), "titulo": meta["titulo"]}


def get_history(limit: int = 20) -> list[dict]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM research_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
