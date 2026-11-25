"""Fontes oficiais prioritárias. Cada fonte declara tipo de acesso."""

FONTES_OFICIAIS = {
    "planalto": {
        "nome": "Planalto — Legislação Federal",
        "base": "https://www.planalto.gov.br",
        "tipo": "web",
        "descricao": "Constituição, leis e decretos federais",
    },
    "camara": {
        "nome": "Câmara dos Deputados — Dados Abertos",
        "base": "https://dadosabertos.camara.leg.br/api/v2",
        "tipo": "api",
        "descricao": "Proposições legislativas federais (API pública)",
    },
    "senado": {
        "nome": "Senado Federal",
        "base": "https://www25.senado.leg.br/web/atividade/materias",
        "tipo": "web",
        "descricao": "Matérias legislativas e leis",
    },
    "cnj_datajud": {
        "nome": "CNJ DataJud — Jurisprudência",
        "base": "https://api-publica.datajud.cnj.jus.br",
        "tipo": "api",
        "descricao": "Decisões judiciais dos tribunais (API pública)",
    },
    "stf": {
        "nome": "Supremo Tribunal Federal",
        "base": "https://portal.stf.jus.br",
        "tipo": "web",
        "descricao": "Jurisprudência constitucional",
    },
    "stj": {
        "nome": "Superior Tribunal de Justiça",
        "base": "https://www.stj.jus.br",
        "tipo": "web",
        "descricao": "Jurisprudência infraconstitucional",
    },
    "tjgo": {
        "nome": "Tribunal de Justiça de Goiás",
        "base": "https://www.tjgo.jus.br",
        "tipo": "web",
        "descricao": "Legislação e decisões do TJ-GO",
    },
    "tjto": {
        "nome": "Tribunal de Justiça do Tocantins",
        "base": "https://www.tjto.jus.br",
        "tipo": "web",
        "descricao": "Legislação e decisões do TJ-TO",
    },
    "tjal": {
        "nome": "Tribunal de Justiça da Bahia",
        "base": "https://www.tjal.jus.br",
        "tipo": "web",
        "descricao": "Legislação e decisões do TJ-AL (Bahia)",
    },
    "web": {
        "nome": "Busca web geral (DuckDuckGo)",
        "base": "https://lite.duckduckgo.com",
        "tipo": "web",
        "descricao": "Busca geral — usar apenas como complemento",
    },
}

TRIBUNAL_POR_ESTADO = {"GO": "tjgo", "TO": "tjto", "BA": "tjba"}
