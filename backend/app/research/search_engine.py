"""Motores de busca: APIs oficiais prioritárias + busca web de fallback."""
import os
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from . import crawler
from .schemas import SourceResult
from .sources import FONTES_OFICIAIS

CNJ_API_KEY = os.environ.get(
    "CNJ_API_KEY",
    "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyR3FmdDdUbnA1ZkE6QQ==",
)


def _camara_search(query: str, max_results: int) -> list[SourceResult]:
    """API oficial da Câmara dos Deputados — proposições legislativas."""
    url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
    params = {"keywords": query, "itens": max_results, "ordem": "DESC", "ordenarPor": "id"}
    try:
        r = httpx.get(url, params=params, timeout=20, headers={"Accept": "application/json"})
        r.raise_for_status()
        dados = r.json().get("dados", [])
    except Exception:
        return []
    out = []
    for p in dados:
        ementa = (p.get("ementa") or "").strip()
        out.append(SourceResult(
            titulo=f"{p.get('siglaTipo','')}{p.get('numero','')}/{p.get('ano','')} — {ementa[:120]}",
            url=p.get("uri", ""),
            fonte="camara",
            trecho=ementa[:500],
            tipo="api",
        ))
    return out


def _datajud_search(query: str, estado: str | None, max_results: int) -> list[SourceResult]:
    """API pública do CNJ DataJud — jurisprudência dos tribunais."""
    tribunal = {"GO": "tjgo", "TO": "tjto", "BA": "tjba"}.get(estado or "", "")
    if not tribunal:
        tribunal = "tjal"  # fallback: maior base disponível
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"
    body = {
        "query": {"match": {"conteudo": query}},
        "size": max_results,
    }
    try:
        r = httpx.post(
            url, json=body, timeout=25,
            headers={"Authorization": f"ApiKey {CNJ_API_KEY}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
    except Exception:
        return []
    out = []
    for h in hits:
        s = h.get("_source", {})
        orgao = s.get("orgaoJulgador", {}).get("nome", "") if isinstance(s.get("orgaoJulgador"), dict) else ""
        numero = s.get("numeroProcesso", "")
        classe = s.get("classe", {}).get("nome", "") if isinstance(s.get("classe"), dict) else ""
        conteudo = (s.get("conteudo") or "")[:600]
        out.append(SourceResult(
            titulo=f"{classe} — {numero}".strip(" —"),
            url=f"https://www.cnj.jus.br",
            fonte="cnj_datajud",
            trecho=f"Órgão: {orgao}\n{conteudo}",
            tipo="api",
        ))
    return out


def _ddg_search(query: str, max_results: int) -> list[SourceResult]:
    """Busca web via DuckDuckGo Lite (fallback, complemento)."""
    try:
        r = httpx.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query}, timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) NeuralJuris/0.1"},
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for a in soup.select("a.result-link")[:max_results]:
            href = a.get("href", "")
            if "uddg=" in href:
                href = urllib.parse.unquote(re.search(r"uddg=([^&]+)", href).group(1))
            snippet_el = a.find_next("td", class_="result-snippet")
            out.append(SourceResult(
                titulo=a.get_text(strip=True)[:150],
                url=href,
                fonte="web",
                trecho=(snippet_el.get_text(" ", strip=True)[:400] if snippet_el else ""),
                tipo="web",
            ))
        return out
    except Exception:
        return []


def _site_restricted_search(query: str, fonte_key: str, max_results: int) -> list[SourceResult]:
    """Busca restrita a um site oficial via DDG (site:dominio)."""
    fonte = FONTES_OFICIAIS.get(fonte_key)
    if not fonte:
        return []
    domain = fonte["base"].split("/")[2]
    return _ddg_search(f"{query} site:{domain}", max_results)


def search(query: str, estado: str | None = None, fontes: list[str] | None = None,
           max_results: int = 5) -> list[SourceResult]:
    """Pesquisa multicamada: APIs oficiais primeiro, web como complemento."""
    fontes = fontes or ["camara", "cnj_datajud", "web"]
    results: list[SourceResult] = []

    if "camara" in fontes:
        results.extend(_camara_search(query, max_results))
    if "cnj_datajud" in fontes or "jurisprudencia" in fontes:
        results.extend(_datajud_search(query, estado, max_results))
    if "web" in fontes:
        # prioriza sites estaduais do estado pesquisado
        if estado == "GO" and "tjgo" not in fontes:
            results.extend(_site_restricted_search(query, "tjgo", max_results // 2 + 1))
        if estado == "TO" and "tjto" not in fontes:
            results.extend(_site_restricted_search(query, "tjto", max_results // 2 + 1))
        if estado == "BA" and "tjal" not in fontes:
            results.extend(_site_restricted_search(query, "tjal", max_results // 2 + 1))
        results.extend(_ddg_search(query, max_results))

    # dedup por URL
    seen, out = set(), []
    for r in results:
        if r.url and r.url not in seen:
            seen.add(r.url)
            out.append(r)
    return out[: max_results * 2]
