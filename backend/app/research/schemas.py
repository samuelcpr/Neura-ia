from pydantic import BaseModel, Field


class ResearchSearchRequest(BaseModel):
    query: str = Field(min_length=3)
    estado: str | None = None
    fontes: list[str] | None = None
    max_resultados: int = Field(default=5, ge=1, le=20)


class ResearchAnalyzeRequest(BaseModel):
    pergunta: str = Field(min_length=3)
    estado: str | None = None
    fontes: list[str] | None = None
    max_fontes: int = Field(default=4, ge=1, le=10)


class CrawlRequest(BaseModel):
    url: str
    profundidade: int = Field(default=1, ge=0, le=2)
    max_paginas: int = Field(default=10, ge=1, le=50)


class SourceResult(BaseModel):
    titulo: str
    url: str
    fonte: str
    trecho: str = ""
    data: str | None = None
    tipo: str = "web"  # api | web | pdf
