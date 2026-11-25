"""Scraper — extração de conteúdo estruturado de páginas HTML."""
import re

from bs4 import BeautifulSoup


def extract_main_content(html: str) -> str:
    """Extrai o conteúdo principal de uma página HTML."""
    soup = BeautifulSoup(html, "html.parser")
    # remove elementos não relacionados ao conteúdo
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    # tenta encontrar área de conteúdo principal
    for selector in ["main", "article", "#content", ".content", "#main"]:
        el = soup.select_one(selector)
        if el and len(el.get_text(strip=True)) > 200:
            return el.get_text("\n", strip=True)
    return soup.get_text("\n", strip=True)


def extract_metadata(html: str, url: str) -> dict:
    """Extrai metadados de uma página HTML."""
    soup = BeautifulSoup(html, "html.parser")
    meta = {"url": url, "titulo": "", "descricao": "", "data": None}
    if soup.title:
        meta["titulo"] = soup.title.get_text(strip=True)[:200]
    desc = soup.find("meta", attrs={"name": "description"})
    if desc:
        meta["descricao"] = desc.get("content", "")[:300]
    # tenta encontrar data em meta tags
    for prop in ["article:published_time", "date", "dc.date"]:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag:
            meta["data"] = tag.get("content", "")
            break
    return meta


def extract_pdf_links(html: str, base_url: str) -> list[str]:
    """Extrai links para PDFs de uma página HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf") or "pdf" in href.lower():
            import urllib.parse
            full_url = urllib.parse.urljoin(base_url, href)
            links.append(full_url)
    return links
