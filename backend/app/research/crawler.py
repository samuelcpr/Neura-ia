"""Crawler com respeito a robots.txt, rate limit e timeouts."""
import os
import time
import urllib.parse
import urllib.robotparser
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = os.environ.get(
    "RESEARCH_USER_AGENT",
    "NeuralJurisBot/0.1 (+https://neuraljuris.local; pesquisa educacional juridica)",
)
REQUEST_DELAY = float(os.environ.get("RESEARCH_DELAY", "1.0"))  # segundos por domínio
TIMEOUT = float(os.environ.get("RESEARCH_TIMEOUT", "20"))
MAX_BYTES = 3_000_000

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _domain(url: str) -> str:
    return urlparse(url).netloc


def allowed(url: str) -> bool:
    """Verifica robots.txt do domínio (cacheado)."""
    domain = _domain(url)
    if domain not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{urlparse(url).scheme}://{domain}/robots.txt")
        try:
            rp.read()
        except Exception:
            pass
        _robots[domain] = rp
    rp = _robots[domain]
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def _rate_limit(domain: str) -> None:
    now = time.time()
    wait = REQUEST_DELAY - (now - _last_hit.get(domain, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[domain] = time.time()


def fetch(url: str) -> tuple[int, bytes, str]:
    """GET com rate limit e robots. Retorna (status, bytes, content_type)."""
    if not allowed(url):
        raise PermissionError(f"robots.txt bloqueia: {url}")
    domain = _domain(url)
    _rate_limit(domain)
    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.status_code, r.content[:MAX_BYTES], r.headers.get("content-type", "")


_TAGS_SKIP = {"script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header"}


def html_to_text(html: str, max_chars: int = 20000) -> str:
    """Extrai texto legível de HTML, priorizando main/article."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_TAGS_SKIP):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines)[:max_chars]


def extract_links(html: str, base_url: str, limit: int = 30) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_domain = _domain(base_url)
    links = []
    for a in soup.find_all("a", href=True):
        href = urllib.parse.urljoin(base_url, a["href"])
        if _domain(href) == base_domain and href not in links:
            links.append(href)
        if len(links) >= limit:
            break
    return links
