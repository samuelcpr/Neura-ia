"""Extração e limpeza de conteúdo de páginas e documentos."""
import re
from pathlib import Path


def clean_text(text: str) -> str:
    """Remove ruído comum de páginas oficiais."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # remove linhas de navegação típicas
    text = re.sub(r"(?im)^(pular para|acessar|menu|buscar|home|início)\s*$", "", text)
    return text.strip()


def detect_metadata(text: str, url: str) -> dict:
    """Tenta extrair data, título e tipo de norma do conteúdo."""
    meta = {"url": url, "titulo": "", "data": None}
    title_match = re.search(r"(?im)^#\s+(.+)$", text)
    if title_match:
        meta["titulo"] = title_match.group(1).strip()[:200]
    date_match = re.search(
        r"(?i)(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}|publicad[oa] em [^\n]{5,40})", text[:3000]
    )
    if date_match:
        meta["data"] = date_match.group(1)
    return meta


def extract_pdf_from_bytes(content: bytes, file_path: Path) -> str:
    from app.services.document import extract_pdf_text

    file_path.write_bytes(content)
    return extract_pdf_text(file_path)
