import hashlib
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app import auth, db
from app.services.document import chunk_text, extract_text
from app.services import embeddings

router = APIRouter(prefix="/editais", tags=["editais"])

DISCIPLINAS_CONHECIDAS = [
    "Direito Constitucional", "Direito Administrativo", "Direito Penal",
    "Direito Processual Penal", "Direito Civil", "Direito Processual Civil",
    "Direito Tributário", "Direito do Trabalho", "Direitos Humanos",
    "Legislação Penal Especial", "Legislação Institucional", "Direito Eleitoral",
    "Direito Ambiental", "Direito Previdenciário", "Língua Portuguesa",
    "Matemática", "Raciocínio Lógico", "Informática", "História do Brasil",
    "História Regional", "Geografia do Brasil", "Geografia Regional",
    "Atualidades", "Administração Pública", "Ética no Serviço Público",
    "Arquivologia", "Legislação Municipal", "Noções de Administração",
]

SINONIMOS = {
    "língua portuguesa": "Língua Portuguesa", "portugues": "Língua Portuguesa",
    "matematica": "Matemática", "raciocinio logico": "Raciocínio Lógico",
    "informatica": "Informática", "historia": "História do Brasil",
    "geografia": "Geografia do Brasil", "atualidades": "Atualidades",
    "administracao publica": "Administração Pública", "etica": "Ética no Serviço Público",
    "arquivologia": "Arquivologia", "direito constitucional": "Direito Constitucional",
    "direito administrativo": "Direito Administrativo", "direito penal": "Direito Penal",
    "processual penal": "Direito Processual Penal", "direito civil": "Direito Civil",
    "processual civil": "Direito Processual Civil", "direito tributario": "Direito Tributário",
    "direito do trabalho": "Direito do Trabalho", "direitos humanos": "Direitos Humanos",
    "legislacao penal": "Legislação Penal Especial", "legislacao institucional": "Legislação Institucional",
    "direito eleitoral": "Direito Eleitoral", "direito ambiental": "Direito Ambiental",
    "direito previdenciario": "Direito Previdenciário",
}


def detect_disciplines(text: str) -> list[dict]:
    low = text.lower()
    found = []
    for nome in DISCIPLINAS_CONHECIDAS:
        key = nome.lower()
        count = low.count(key)
        if count == 0 and key in SINONIMOS.values():
            pass
        if count:
            found.append({"disciplina": nome, "ocorrencias": count})
    # sinonimos que nao sao nome completo
    for sin, nome in SINONIMOS.items():
        if nome in DISCIPLINAS_CONHECIDAS and sin != nome.lower():
            extra = len(re.findall(re.escape(sin), low))
            if extra and not any(f["disciplina"] == nome for f in found):
                found.append({"disciplina": nome, "ocorrencias": extra})
    found.sort(key=lambda x: -x["ocorrencias"])
    return found


@router.post("/upload", dependencies=[Depends(auth.require_auth)])
async def upload_edital(
    file: UploadFile = File(...),
    estado: str = Form("FEDERAL"),
    orgao: str | None = Form(None),
    cargo: str | None = Form(None),
    banca: str | None = Form(None),
    data_concurso: str | None = Form(None),
):
    estado = estado.upper()
    if estado not in db.ESTADOS:
        raise HTTPException(400, f"Estado inválido: {estado}")
    filename = Path(file.filename or "edital.pdf").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(400, "Formato não suportado")

    content = await file.read()
    dedup = hashlib.sha256(content).hexdigest()
    file_path = db.UPLOAD_DIR / f"edital_{dedup[:16]}{suffix}"
    file_path.write_bytes(content)

    try:
        text = extract_text(file_path, suffix)
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Falha ao extrair texto: {e}")
    if not text:
        file_path.unlink(missing_ok=True)
        raise HTTPException(422, "Edital sem texto extraível.")

    text_file = db.TEXT_DIR / f"edital_{dedup[:16]}.txt"
    text_file.write_text(text, encoding="utf-8")

    disciplinas = detect_disciplines(text)

    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM documents WHERE dedup_hash = ?", (dedup,)
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicado": True}

        cur = conn.execute(
            """INSERT INTO documents
               (filename, original_name, estado, disciplina, assunto, tipo, file_path,
                text_path, chars, status, dedup_hash)
               VALUES (?,?,?,?,?,'edital',?,?,?,'processado',?)""",
            (file_path.name, filename, estado, "Edital", cargo or orgao,
             str(file_path), str(text_file), len(text), dedup),
        )
        doc_id = cur.lastrowid
        for seq, chunk in enumerate(chunk_text(text)):
            conn.execute(
                "INSERT INTO chunks (document_id, seq, content) VALUES (?,?,?)",
                (doc_id, seq, chunk),
            )
        embeddings.embed_chunks_sync(conn, doc_id)
        cur2 = conn.execute(
            """INSERT INTO editais
               (document_id, estado, orgao, cargo, banca, data_concurso, disciplinas_detectadas)
               VALUES (?,?,?,?,?,?,?)""",
            (doc_id, estado, orgao, cargo, banca, data_concurso,
             json.dumps(disciplinas, ensure_ascii=False)),
        )
        edital_id = cur2.lastrowid

    return {
        "edital_id": edital_id, "document_id": doc_id, "chars": len(text),
        "disciplinas_detectadas": disciplinas,
    }


@router.get("")
def list_editais(estado: str | None = None):
    query = """SELECT e.*, d.original_name, d.chars FROM editais e
               JOIN documents d ON d.id = e.document_id"""
    params: list = []
    if estado:
        query += " WHERE e.estado = ?"
        params.append(estado.upper())
    query += " ORDER BY e.created_at DESC"
    with db.get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["disciplinas_detectadas"] = json.loads(d["disciplinas_detectadas"] or "[]")
        out.append(d)
    return {"total": len(out), "editais": out}


@router.get("/{eid}")
def get_edital(eid: int):
    with db.get_conn() as conn:
        row = conn.execute(
            """SELECT e.*, d.original_name, d.chars FROM editais e
               JOIN documents d ON d.id = e.document_id WHERE e.id = ?""",
            (eid,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Edital não encontrado")
        d = dict(row)
        d["disciplinas_detectadas"] = json.loads(d["disciplinas_detectadas"] or "[]")
    return d
