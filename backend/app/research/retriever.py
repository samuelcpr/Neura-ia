"""Recuperação híbrida: base local (chunks+embeddings) + resultados web."""
import json

from app import db
from app.services import embeddings, ollama
from app.services.document import chunk_text

from .schemas import SourceResult
from .search_engine import search as web_search


def local_chunks(estado: str | None, query: str, top_k: int = 5) -> list[dict]:
    """Recupera chunks locais ranqueados (embedding + keyword)."""
    query_sql = """
        SELECT c.id, c.content, c.embedding, d.original_name, d.estado, d.disciplina, d.assunto
        FROM chunks c JOIN documents d ON d.id = c.document_id
    """
    params: list = []
    if estado and estado.upper() in db.ESTADOS:
        query_sql += " WHERE d.estado = ? OR d.estado = 'FEDERAL'"
        params.append(estado.upper())
    with db.get_conn() as conn:
        rows = conn.execute(query_sql, params).fetchall()
    chunks = [dict(r) for r in rows]
    if not chunks:
        return []
    return ollama.retrieve(query, chunks, top_k=top_k)


def web_results_to_chunks(results: list[SourceResult]) -> list[dict]:
    """Converte resultados web em formato de chunk para o pipeline de resposta."""
    out = []
    for i, r in enumerate(results):
        content = f"{r.titulo}\n{r.trecho}\nFonte: {r.fonte} | URL: {r.url}"
        out.append({
            "id": f"web-{i}",
            "content": content,
            "original_name": f"[{r.fonte}] {r.titulo[:60]}",
            "estado": "WEB",
            "disciplina": None,
            "assunto": r.fonte,
            "score": 0.5,
        })
    return out


def index_web_document(result: SourceResult, estado: str = "FEDERAL") -> int | None:
    """Indexa um documento web na base de conhecimento (tipo='web')."""
    if not result.trecho or len(result.trecho) < 100:
        return None
    import hashlib

    dedup = hashlib.sha256(result.url.encode()).hexdigest()
    doc_name = f"web_{dedup[:12]}.txt"
    file_path = db.UPLOAD_DIR / doc_name
    text_file = db.TEXT_DIR / f"web_{dedup[:12]}.txt"

    text_file.write_text(result.trecho, encoding="utf-8")
    file_path.write_text(result.trecho, encoding="utf-8")

    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM documents WHERE dedup_hash = ?", (dedup,)
        ).fetchone()
        if existing:
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO documents
               (filename, original_name, estado, disciplina, assunto, tipo, file_path,
                text_path, chars, status, dedup_hash)
               VALUES (?,?,?,?,?,'web',?,?,?,?,'processado',?)""",
            (doc_name, f"[{result.fonte}] {result.titulo[:80]}", estado,
             None, result.fonte, str(file_path), str(text_file),
             len(result.trecho), dedup),
        )
        doc_id = cur.lastrowid
        for seq, chunk in enumerate(chunk_text(result.trecho, size=800, overlap=100)):
            conn.execute(
                "INSERT INTO chunks (document_id, seq, content) VALUES (?,?,?)",
                (doc_id, seq, chunk),
            )
        embeddings.embed_chunks_sync(conn, doc_id)
    return doc_id
