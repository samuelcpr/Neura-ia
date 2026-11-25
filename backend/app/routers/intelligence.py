"""Motores especializados: FIRAC+, geração de questões, mapas mentais, aulas."""
import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import auth, db
from app.routers.documents import ask_load_chunks
from app.services import ollama

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class TemaRequest(BaseModel):
    tema: str = Field(min_length=3)
    estado: str | None = None
    detalhes: str | None = None


class FiracRequest(BaseModel):
    pergunta: str = Field(min_length=10)
    estado: str | None = None
    incluir_jurisprudencia: bool = True


class QuestaoRequest(BaseModel):
    disciplina: str
    assunto: str | None = None
    estado: str = "FEDERAL"
    banca: str | None = None
    dificuldade: Literal["facil", "media", "dificil"] = "media"
    estilo: str | None = None


def _contexto(tema: str, estado: str | None, top_k: int = 5) -> str:
    chunks = ask_load_chunks(estado)
    relevant = ollama.retrieve(tema, chunks, top_k=top_k) if chunks else []
    return "\n\n---\n\n".join(
        "[Fonte: " + c["original_name"] + " | Estado: " + c["estado"] + "]" + chr(10) + c["content"]
        for c in relevant
    )


# ============ ANÁLISE JURÍDICA FIRAC+ ============

@router.post("/firac")
def analise_juridica(req: FiracRequest):
    """Análise jurídica estruturada no método FIRAC+ com fundamentação."""
    ctx = _contexto(req.pergunta, req.estado, top_k=6)
    jurisp = (
        "Busque entendimentos consolidados. Se não houver fonte no contexto, diga explicitamente que não foi possível verificar."
        if req.incluir_jurisprudencia
        else "Omitido a pedido do usuário."
    )
    prompt = (
        "Você é a NeuralJuris AI, especialista em análise jurídica para concursos de GO/TO/BA.\n\n"
        "Analise a seguinte questão jurídica usando o método FIRAC+ e responda em português, em markdown, com EXATAMENTE estas seções:\n\n"
        "## Fatos\nIdentifique os fatos relevantes da questão.\n\n"
        "## Problema Jurídico\nDelimite a questão a ser respondida.\n\n"
        "## Normas Aplicáveis\nListe os dispositivos legais/princípios pertinentes. Use SOMENTE normas que existam — nunca invente artigos. Se não tiver certeza do número do artigo, cite o nome da lei/constituição sem número.\n\n"
        "## Interpretação e Fundamentação\nAnálise gramatical/literal e sistemática. Mencione métodos hermenêuticos aplicáveis (literal, sistemático, teleológico, etc).\n\n"
        "## Jurisprudência e Doutrina\n" + jurisp + "\n\n"
        "## Aplicação aos Fatos\nSubsunsão: relacione normas e fatos.\n\n"
        "## Conclusão\nResultado, ressalvas e eventuais divergências doutrinárias/jurisprudenciais.\n\n"
        "## Fontes Consultadas\nListe as fontes do contexto utilizadas (documento + estado). Se algo for interpretação sua (nível 3 — não verificável), identifique como \"interpretação da IA\".\n\n"
        "CONTEXTO DA BASE DE CONHECIMENTO:\n" + (ctx if ctx else "(sem documentos relevantes na base local)") + "\n\n"
        "QUESTÃO: " + req.pergunta + "\n\nRESPOSTA FIRAC+:"
    )
    resposta = ollama.generate_raw(prompt, timeout=600)
    if not resposta:
        raise HTTPException(503, "Modelo de IA indisponível")
    return {"pergunta": req.pergunta, "estado": req.estado, "analise": resposta,
            "fontes_contexto": len(ctx.split("---")) if ctx else 0}


# ============ GERAÇÃO DE MAPAS MENTAIS ============

def _mermaid_from_corpus(tema: str, estado: str | None) -> str | None:
    """Constrói mapa mental determinístico a partir da base de conhecimento."""
    chunks = ask_load_chunks(estado)
    if not chunks:
        return None
    relevant = ollama.retrieve(tema, chunks, top_k=8)
    if not relevant:
        return None

    disciplinas: dict[str, list[str]] = {}
    for c in relevant:
        disc = c.get("disciplina") or "Geral"
        ass = c.get("assunto") or c.get("original_name", "")[:40]
        disciplinas.setdefault(disc, [])
        if ass not in disciplinas[disc] and len(disciplinas[disc]) < 4:
            disciplinas[disc].append(ass)

    if not disciplinas:
        return None

    lines = ["mindmap", "  root((" + tema[:40] + "))"]
    for disc, assuntos in list(disciplinas.items())[:6]:
        lines.append("    " + re.sub(r"[^\wÀ-ÿ ()/-]", "", disc)[:30])
        for a in assuntos[:3]:
            lines.append("      " + re.sub(r"[^\wÀ-ÿ ()/-]", "", a)[:35])
    return "\n".join(lines)


@router.post("/mapa-mental")
def gerar_mapa(req: TemaRequest):
    """Gera mapa mental: tenta LLM, senão constrói da base de conhecimento."""
    ctx = _contexto(req.tema, req.estado, top_k=4)
    mermaid = _mermaid_from_corpus(req.tema, req.estado)
    origem = "base_conhecimento"

    if not mermaid:
        ctx_block = ("CONTEXTO DE REFERÊNCIA:\n" + ctx[:3000]) if ctx else ""
        detalhes = ("DETALHES: " + req.detalhes) if req.detalhes else ""
        prompt = (
            "Gere um MAPA MENTAL em sintaxe Mermaid (mindmap) sobre o tema abaixo, voltado a concursos públicos.\n\n"
            "REGRAS:\n"
            "- Responda APENAS com o código Mermaid, sem explicações, sem markdown\n"
            "- Use a sintaxe: mindmap seguido de linhas indentadas com nós\n"
            "- Estrutura: tema central, depois 3-6 disciplinas/tópicos, depois 2-4 subitens cada\n"
            "- Máximo ~25 nós, foco no que cai em prova\n"
            "- Português do Brasil\n\n"
            + (ctx_block + "\n\n" if ctx_block else "")
            + "TEMA: " + req.tema + "\n" + detalhes + "\n\nCÓDIGO MERMAID:"
        )
        llm = ollama.generate_raw(prompt, timeout=300)
        if llm:
            llm = re.sub(r"^```(?:mermaid)?\s*|\s*```$", "", llm.strip(), flags=re.MULTILINE)
            if "mindmap" in llm.lower():
                mermaid = llm.strip()
                origem = "ia"

    if not mermaid:
        mermaid = (
            "mindmap\n"
            "  root((" + req.tema + "))\n"
            "    Conteúdo Programático\n"
            "    Legislação Aplicável\n"
            "    Questões Frequentes\n"
            "    Jurisprudência"
        )
        origem = "generico"

    return {"tema": req.tema, "mermaid": mermaid, "origem": origem, "contexto_usado": bool(ctx)}


# ============ GERAÇÃO DE AULAS ============

@router.post("/aula")
def gerar_aula(req: TemaRequest):
    """Gera aula completa em markdown: explicação, o que memorizar, pegadinhas, questões."""
    ctx = _contexto(req.tema, req.estado, top_k=6)
    base_block = (
        "BASE DE CONHECIMENTO (use como fonte, cite documentos):\n" + ctx[:5000]
        if ctx
        else "Sem documentos na base — baseie-se em conhecimento geral, sinalizando incertezas."
    )
    foco = ("FOCO: " + req.detalhes) if req.detalhes else ""
    prompt = (
        "Você é a NeuralJuris AI, professora de cursinho para concursos de GO/TO/BA.\n\n"
        "Gere uma AULA COMPLETA sobre o tema abaixo, em markdown, seguindo esta estrutura:\n\n"
        "## Objetivo de Aprendizagem\nO que o aluno deve saber ao final.\n\n"
        "## O Que Você Precisa Compreender\nExplicação clara e direta, em tópicos.\n\n"
        "## O Que Memorizar\nLista objetiva dos pontos de prova (números, prazos, regras, exceções).\n\n"
        "## Como Cai em Prova\nPadrões de questão, pegadinhas clássicas e confusões comuns.\n\n"
        "## Exemplos Práticos\n1-2 situações aplicadas (de preferência de GO/TO/BA quando o tema permitir).\n\n"
        "## Questão Comentada\nUma questão de múltipla escolha autoral com gabarito e comentário.\n\n"
        "## Resumo em 5 Linhas\nPara revisão rápida.\n\n"
        + base_block + "\n\n"
        "TEMA: " + req.tema + "\n" + foco + "\n\nAULA:"
    )
    aula = ollama.generate_raw(prompt, timeout=600)
    if not aula:
        raise HTTPException(503, "Modelo de IA indisponível")
    return {"tema": req.tema, "aula": aula, "fontes": len(ctx.split("---")) if ctx else 0}


# ============ GERAÇÃO DE QUESTÕES COM VALIDAÇÃO ============

QUESTAO_SCHEMA = """{
  "disciplina": "string",
  "assunto": "string",
  "tipo": "multipla_escolha",
  "nivel": "facil|medio|dificil",
  "banca_referencia": "string ou null",
  "enunciado": "string",
  "alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
  "gabarito": "A|B|C|D|E",
  "fundamentacao": "string — explicação jurídica da resposta",
  "base_legal": "string — lei/artigo se aplicável",
  "status_validacao": "pendente"
}"""


@router.post("/questao", dependencies=[Depends(auth.require_auth)])
def gerar_questao(req: QuestaoRequest):
    """Gera questão estruturada (JSON) + validação independente do gabarito."""
    ctx = _contexto(req.disciplina + " " + (req.assunto or ""), req.estado, top_k=4)

    banca_txt = ("Banca de referência: " + req.banca) if req.banca else ""
    estilo_txt = ("Estilo pedido: " + req.estilo) if req.estilo else ""
    assunto_txt = ("Assunto: " + req.assunto) if req.assunto else ""
    ctx_block = ("CONTEXTO DA BASE:\n" + ctx[:4000]) if ctx else ""

    prompt_geracao = (
        "Você é elaborador de questões de concurso público (bancas AOCP, Cebraspe, FGV, FCC, Vunesp, IBFC, Consulplan, Quadrix).\n\n"
        "Gere UMA questão de múltipla escolha (5 alternativas A-E) sobre:\n"
        "Disciplina: " + req.disciplina + "\n" + assunto_txt + "\n"
        "Estado foco: " + req.estado + "\n" + banca_txt + "\n"
        "Dificuldade: " + req.dificuldade + "\n" + estilo_txt + "\n\n"
        "REGRAS:\n"
        "- Apenas UMA alternativa correta, plausível e defensável\n"
        "- Alternativas com comprimento e estilo parecidos (sem 'todos os anteriores')\n"
        "- Enunciado claro, sem pegadinha maliciosa\n"
        "- Se envolver legislação, use APENAS dispositivos reais — nunca invente artigos\n"
        "- fundamentacao: explique por que a correta está certa E por que as erradas falham\n\n"
        + (ctx_block + "\n\n" if ctx_block else "")
        + "Responda APENAS com JSON válido neste schema:\n" + QUESTAO_SCHEMA
    )

    questao = ollama.generate_json(prompt_geracao)
    if not questao or "enunciado" not in questao:
        raise HTTPException(503, "Falha ao gerar questão (modelo indisponível ou resposta inválida)")

    # ---- Validação independente (segunda passada) ----
    alts = questao.get("alternativas", {})
    gab = questao.get("gabarito", "")
    validacao = {"gabarito_confere": None, "problemas": [], "aprovada": False}

    if isinstance(alts, dict) and set(alts.keys()) >= {"A", "B", "C", "D", "E"} and gab in alts:
        alts_txt = "\n".join(k + ") " + str(v) for k, v in alts.items())
        prompt_val = (
            "Você é revisor de qualidade de questões de concurso.\n\n"
            "Questão:\nENUNCIADO: " + str(questao.get("enunciado", "")) + "\n"
            "ALTERNATIVAS:\n" + alts_txt + "\n"
            "GABARITO ALEGADO: " + str(gab) + "\n\n"
            "TAREFA: Verifique de forma INDEPENDENTE qual alternativa está correta. Responda APENAS JSON:\n"
            '{"gabarito_correto": "A|B|C|D|E", "confianca": "alta|media|baixa", "problemas": ["lista de problemas se houver"]}'
        )
        rev = ollama.generate_json(prompt_val)
        if rev and rev.get("gabarito_correto") in alts:
            validacao["gabarito_confere"] = rev["gabarito_correto"] == gab
            validacao["confianca"] = rev.get("confianca")
            validacao["problemas"] = rev.get("problemas", [])
            problemas_criticos = [
                p for p in validacao["problemas"]
                if any(w in str(p).lower() for w in ("gabarito", "correta", "alternativa"))
            ]
            validacao["aprovada"] = (
                bool(validacao["gabarito_confere"])
                and rev.get("confianca") in ("alta", "media")
                and not problemas_criticos
            )
            if not validacao["gabarito_confere"]:
                validacao["problemas"].append("Revisor aponta gabarito " + str(rev["gabarito_correto"]) + ", não " + str(gab))

    questao["status_validacao"] = "aprovada" if validacao["aprovada"] else "pendente_revisao"
    questao["validacao"] = validacao

    # ---- Persiste no banco de questões ----
    if validacao["aprovada"]:
        with db.get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO questions
                   (enunciado, alternativas, gabarito, estado, concurso, cargo, disciplina,
                    assunto, banca, dificuldade, origem, explicacao)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (questao["enunciado"], json.dumps(alts, ensure_ascii=False), gab,
                 req.estado.upper(), None, None, req.disciplina, req.assunto,
                 req.banca, req.dificuldade, "autoral", questao.get("fundamentacao")),
            )
            questao["id_salvo"] = cur.lastrowid

    return questao


# ============ FLASHCARDS ============

@router.post("/flashcards")
def gerar_flashcards(req: TemaRequest):
    """Gera flashcards de memorização em JSON."""
    ctx = _contexto(req.tema, req.estado, top_k=4)
    detalhes = ("Detalhes: " + req.detalhes) if req.detalhes else ""
    ctx_block = ("Contexto de referência:\n" + ctx[:3000]) if ctx else ""
    prompt = (
        "Gere 8-12 FLASHCARDS de estudo sobre: " + req.tema + "\n"
        + detalhes + "\n" + ctx_block + "\n\n"
        'Responda APENAS JSON: {"flashcards": [{"frente": "pergunta curta", "verso": "resposta objetiva"}]}'
    )
    data = ollama.generate_json(prompt)
    if not data or "flashcards" not in data:
        raise HTTPException(503, "Falha ao gerar flashcards")
    return {"tema": req.tema, "flashcards": data["flashcards"]}
