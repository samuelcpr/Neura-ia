import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "neuraljuris.db"
UPLOAD_DIR = DATA_DIR / "uploads"
TEXT_DIR = DATA_DIR / "text"

ESTADOS = ("GO", "TO", "BA", "FEDERAL")
ORIGENS_QUESTAO = ("oficial", "autoral", "adaptada")
DIFICULDADES = ("facil", "media", "dificil")


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'FEDERAL',
                disciplina TEXT,
                assunto TEXT,
                tipo TEXT NOT NULL DEFAULT 'pdf',
                file_path TEXT NOT NULL,
                text_path TEXT,
                chars INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'processado',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                seq INTEGER NOT NULL,
                content TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enunciado TEXT NOT NULL,
                alternativas TEXT NOT NULL,
                gabarito TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'FEDERAL',
                concurso TEXT,
                cargo TEXT,
                disciplina TEXT NOT NULL,
                assunto TEXT,
                subassunto TEXT,
                artigo_lei TEXT,
                banca TEXT,
                ano INTEGER,
                dificuldade TEXT NOT NULL DEFAULT 'media',
                origem TEXT NOT NULL DEFAULT 'autoral',
                explicacao TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                resposta TEXT NOT NULL,
                correta INTEGER NOT NULL,
                tempo_segundos REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS editais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                estado TEXT NOT NULL DEFAULT 'FEDERAL',
                orgao TEXT,
                cargo TEXT,
                banca TEXT,
                data_concurso TEXT,
                disciplinas_detectadas TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS research_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                estado TEXT,
                resultados TEXT,
                resposta TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_documents_estado ON documents(estado);
            CREATE INDEX IF NOT EXISTS idx_questions_estado ON questions(estado);
            CREATE INDEX IF NOT EXISTS idx_questions_disciplina ON questions(disciplina);
            CREATE INDEX IF NOT EXISTS idx_attempts_question ON attempts(question_id);
            """
        )
        _ensure_column(conn, "chunks", "embedding", "TEXT")
        _ensure_column(conn, "documents", "dedup_hash", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
