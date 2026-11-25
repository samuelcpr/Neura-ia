"""Gerencia citações e referências verificáveis."""
from datetime import datetime, timezone

from .schemas import SourceResult


def format_citation(src: SourceResult, index: int) -> str:
    data = src.data or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"[{index}] {src.titulo} — {src.fonte} — consultado em {data} — {src.url}"


def build_references(results: list[SourceResult]) -> str:
    if not results:
        return "Nenhuma fonte externa foi utilizada nesta resposta."
    lines = ["FONTES CONSULTADAS:"]
    for i, r in enumerate(results, 1):
        lines.append(format_citation(r, i))
    return "\n".join(lines)


def is_safe_url(url: str) -> bool:
    """Valida URL antes de citar ou abrir."""
    return url.startswith(("http://", "https://")) and " " not in url
