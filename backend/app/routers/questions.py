from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app import auth, db

router = APIRouter(prefix="/questions", tags=["questions"])


class QuestionIn(BaseModel):
    enunciado: str = Field(min_length=10)
    alternativas: dict[str, str] = Field(min_length=2)
    gabarito: str
    estado: str = "FEDERAL"
    concurso: str | None = None
    cargo: str | None = None
    disciplina: str
    assunto: str | None = None
    subassunto: str | None = None
    artigo_lei: str | None = None
    banca: str | None = None
    ano: int | None = None
    dificuldade: str = "media"
    origem: str = "autoral"
    explicacao: str | None = None


class AnswerIn(BaseModel):
    resposta: str
    tempo_segundos: float | None = None


def _validate(q: QuestionIn):
    q.estado = q.estado.upper()
    if q.estado not in db.ESTADOS:
        raise HTTPException(400, f"Estado inválido: {q.estado}")
    if q.gabarito not in q.alternativas:
        raise HTTPException(400, f"Gabarito deve ser uma das alternativas: {list(q.alternativas)}")
    if q.dificuldade not in db.DIFICULDADES:
        raise HTTPException(400, f"Dificuldade inválida: {q.dificuldade}")
    if q.origem not in db.ORIGENS_QUESTAO:
        raise HTTPException(400, f"Origem inválida: {q.origem}")


@router.post("", dependencies=[Depends(auth.require_auth)])
def create_question(q: QuestionIn):
    _validate(q)
    import json

    with db.get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO questions
               (enunciado, alternativas, gabarito, estado, concurso, cargo, disciplina,
                assunto, subassunto, artigo_lei, banca, ano, dificuldade, origem, explicacao)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (q.enunciado, json.dumps(q.alternativas, ensure_ascii=False), q.gabarito,
             q.estado, q.concurso, q.cargo, q.disciplina, q.assunto, q.subassunto,
             q.artigo_lei, q.banca, q.ano, q.dificuldade, q.origem, q.explicacao),
        )
        return {"id": cur.lastrowid}


@router.get("")
def list_questions(
    estado: str | None = None,
    disciplina: str | None = None,
    banca: str | None = None,
    origem: str | None = None,
    limit: int = Query(50, le=200),
):
    import json

    query = "SELECT * FROM questions"
    clauses, params = [], []
    for col, val in (("estado", estado), ("disciplina", disciplina),
                     ("banca", banca), ("origem", origem)):
        if val:
            clauses.append(f"{col} = ?")
            params.append(val.upper() if col == "estado" else val)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with db.get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["alternativas"] = json.loads(d["alternativas"])
        out.append(d)
    return {"total": len(out), "questions": out}


@router.get("/{qid}")
def get_question(qid: int):
    import json

    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
        if not row:
            raise HTTPException(404, "Questão não encontrada")
        d = dict(row)
        d["alternativas"] = json.loads(d["alternativas"])
        stats = conn.execute(
            "SELECT COUNT(*) AS total, SUM(correta) AS acertos FROM attempts WHERE question_id = ?",
            (qid,),
        ).fetchone()
        d["estatisticas"] = dict(stats)
    return d


@router.post("/{qid}/answer")
def answer_question(qid: int, req: AnswerIn):
    with db.get_conn() as conn:
        q = conn.execute("SELECT gabarito FROM questions WHERE id = ?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, "Questão não encontrada")
        correta = 1 if req.resposta.strip().upper() == q["gabarito"] else 0
        conn.execute(
            "INSERT INTO attempts (question_id, resposta, correta, tempo_segundos) VALUES (?,?,?,?)",
            (qid, req.resposta, correta, req.tempo_segundos),
        )
        return {"correta": bool(correta), "gabarito": q["gabarito"]}


@router.delete("/{qid}", dependencies=[Depends(auth.require_auth)])
def delete_question(qid: int):
    with db.get_conn() as conn:
        if not conn.execute("SELECT id FROM questions WHERE id = ?", (qid,)).fetchone():
            raise HTTPException(404, "Questão não encontrada")
        conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    return {"deleted": qid}


@router.get("/stats/summary")
def stats_summary():
    with db.get_conn() as conn:
        total_q = conn.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"]
        total_a = conn.execute("SELECT COUNT(*) c FROM attempts").fetchone()["c"]
        acertos = conn.execute("SELECT COALESCE(SUM(correta),0) c FROM attempts").fetchone()["c"]
        by_disc = conn.execute(
            """SELECT q.disciplina, COUNT(*) total,
                      SUM(CASE WHEN a.correta=1 THEN 1 ELSE 0 END) acertos
               FROM attempts a JOIN questions q ON q.id = a.question_id
               GROUP BY q.disciplina ORDER BY total DESC"""
        ).fetchall()
        by_estado = conn.execute(
            "SELECT estado, COUNT(*) c FROM questions GROUP BY estado"
        ).fetchall()
    return {
        "questoes": total_q,
        "tentativas": total_a,
        "taxa_acerto": round(acertos / total_a * 100, 1) if total_a else None,
        "por_disciplina": [dict(r) for r in by_disc],
        "questoes_por_estado": {r["estado"]: r["c"] for r in by_estado},
    }
