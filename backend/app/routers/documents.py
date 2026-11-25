import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app import auth, db
from app.services import embeddings
from app.services.document import chunk_text, extract_text
from app.services.ocr import ocr_pdf
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", dependencies=[Depends(auth.require_auth)])
async def upload_document(
    file: UploadFile = File(...),
    estado: str = Form("FEDERAL"),
    disciplina: str | None = Form(None),
    assunto: str | None = Form(None),
):
    estado = estado.upper()
    if estado not in db.ESTADOS:
        raise HTTPException(400, f"Estado inválido. Use um de: {', '.join(db.ESTADOS)}")

    filename = Path(file.filename or "documento").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"Formato não suportado. Aceitos: {', '.join(sorted(SUPPORTED))}")

    safe_name = f"{db.UPLOAD_DIR}/doc_{Path(filename).stem[:60]}{suffix}"
    content = await file.read()
    if not content:
        raise HTTPException(400, "Arquivo vazio.")

    dedup = hashlib.sha256(content).hexdigest()
    file_path = Path(safe_name)
    file_path.write_bytes(content)

    try:
        text = extract_text(file_path, suffix)
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Não foi possível extrair texto do arquivo: {e}")

    if not text and suffix == ".pdf":
        try:
            text = ocr_pdf(file_path)
        except Exception:
            text = ""

    if not text:
        file_path.unlink(missing_ok=True)
        raise HTTPException(422, "Arquivo sem texto extraível (PDF digitalizado sem OCR disponível).")

    text_file = db.TEXT_DIR / f"{file_path.stem}.txt"
    text_file.write_text(text, encoding="utf-8")

    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM documents WHERE dedup_hash = ?", (dedup,)
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicado": True}

        cur = conn.execute(
            """INSERT INTO documents
               (filename, original_name, estado, disciplina, assunto, tipo, file_path, text_path, chars, status, dedup_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processado', ?)""",
            (file_path.name, filename, estado, disciplina, assunto,
             suffix.lstrip("."), str(file_path), str(text_file), len(text), dedup),
        )
        doc_id = cur.lastrowid

        chunks = chunk_text(text)
        for seq, chunk in enumerate(chunks):
            conn.execute(
                "INSERT INTO chunks (document_id, seq, content) VALUES (?, ?, ?)",
                (doc_id, seq, chunk),
            )
        embedded = embeddings.embed_chunks_sync(conn, doc_id)

    return {"id": doc_id, "filename": filename, "chars": len(text),
            "chunks": len(chunks), "embeddings": embedded}


@router.get("")
def list_documents(estado: str | None = None, disciplina: str | None = None):
    query = "SELECT id, original_name, estado, disciplina, assunto, chars, status, created_at FROM documents"
    clauses, params = [], []
    if estado:
        clauses.append("estado = ?")
        params.append(estado.upper())
    if disciplina:
        clauses.append("disciplina = ?")
        params.append(disciplina)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"

    with db.get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return {"total": len(rows), "documents": [dict(r) for r in rows]}


@router.get("/search")
def search_documents(q: str, estado: str | None = None, top_k: int = 10):
    from app.services import ollama

    chunks = ask_load_chunks(estado)
    results = ollama.retrieve(q, chunks, top_k=top_k)
    return {"query": q, "total": len(results), "results": results}


@router.get("/{doc_id}")
def get_document(doc_id: int):
    with db.get_conn() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(404, "Documento não encontrado.")
        chunks = conn.execute(
            "SELECT seq, substr(content, 1, 300) AS preview FROM chunks WHERE document_id = ? ORDER BY seq",
            (doc_id,),
        ).fetchall()
    return {**dict(doc), "chunks": [dict(c) for c in chunks]}


def ask_load_chunks(estado: str | None = None) -> list[dict]:
    query = """
        SELECT c.id, c.content, c.embedding, d.original_name, d.estado, d.disciplina, d.assunto
        FROM chunks c JOIN documents d ON d.id = c.document_id
    """
    params: list = []
    if estado and estado.upper() in db.ESTADOS:
        query += " WHERE d.estado = ? OR d.estado = 'FEDERAL'"
        params.append(estado.upper())
    with db.get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.delete("/{doc_id}", dependencies=[Depends(auth.require_auth)])
def delete_document(doc_id: int):
    with db.get_conn() as conn:
        doc = conn.execute("SELECT file_path, text_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(404, "Documento não encontrado.")
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    for p in (doc["file_path"], doc["text_path"]):
        if p:
            Path(p).unlink(missing_ok=True)
    return {"deleted": doc_id}
