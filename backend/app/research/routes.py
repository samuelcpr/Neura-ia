from fastapi import APIRouter, Depends

from app import auth

from . import research_service
from .schemas import CrawlRequest, ResearchAnalyzeRequest, ResearchSearchRequest
from .sources import FONTES_OFICIAIS

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/search")
def search(req: ResearchSearchRequest):
    """Pesquisa em fontes oficiais e web. Retorna resultados com URL e trechos."""
    return research_service.search(req)


@router.post("/analyze")
def analyze(req: ResearchAnalyzeRequest):
    """Pesquisa profunda: busca, extrai, indexa e gera resposta fundamentada com citações."""
    return research_service.analyze(req)


@router.post("/crawl", dependencies=[Depends(auth.require_auth)])
def crawl(req: CrawlRequest):
    """Faz crawl de uma URL específica e indexa o conteúdo na base de conhecimento."""
    return research_service.crawl_and_index(req.url)


@router.get("/history")
def history(limit: int = 20):
    """Histórico de pesquisas realizadas."""
    return {"total": len(research_service.get_history(limit)),
            "pesquisas": research_service.get_history(limit)}


@router.get("/sources")
def sources():
    """Lista fontes oficiais disponíveis para pesquisa."""
    return {"fontes": FONTES_OFICIAIS}
