# ⚖️ NeuralJuris AI

Plataforma brasileira de **IA para concursos públicos** (Goiás, Tocantins e Bahia), 100% local: FastAPI + Ollama + Kokoro TTS + SQLite, empacotada em Docker.

Chat inteligente com RAG sobre seus documentos, pesquisa em fontes oficiais, geração de questões/aulas/mapas mentais, avatar animado com leitura de respostas em voz neural — tudo offline e gratuito.

---

## 🚀 Como iniciar (passo a passo)

### Pré-requisitos

- **Docker** + **Docker Compose** instalados
- ~8 GB de RAM livre (modelos rodam localmente)
- ~10 GB de disco para imagens e modelos

### 1. Clone e configure

```bash
git clone <URL-DO-SEU-REPO> NeuralJuris
cd NeuralJuris
cp .env.example .env   # se não existir, crie manualmente (veja abaixo)
```

### 2. Arquivo `.env`

```env
DATA_DIR=/data
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
EMBED_MODEL=nomic-embed-text
EMBEDDINGS_ENABLED=true
OCR_MAX_PAGES=15
OCR_LANG=por
ADMIN_USER=admin
ADMIN_PASSWORD=troque-esta-senha
AUTH_SECRET=uma-string-aleatoria-longa
RESEARCH_ENABLED=true
RESEARCH_DELAY=1.0
RESEARCH_TIMEOUT=30
CNJ_API_KEY=
```

> ⚠️ **Nunca commite o `.env`** — ele contém senha e segredo. Já está no `.gitignore`.

### 3. Suba os containers

```bash
docker compose up -d --build
```

Primeira vez demora (~10 min): baixa imagens, instala dependências (inclui **torch CPU** para o TTS) e baixa os modelos de IA.

### 4. Baixe os modelos de IA (Ollama)

```bash
docker exec neuraljuris-ollama ollama pull llama3.2:1b
docker exec neuraljuris-ollama ollama pull nomic-embed-text
```

### 5. Acesse

| Recurso | URL |
|---|---|
| 💬 Chat (interface) | http://localhost:8000/ui |
| 📚 Docs da API | http://localhost:8000/docs |
| ❤️ Health check | http://localhost:8000/health |

Login para ações protegidas (upload, questões): `admin` / senha do `.env`

### 6. Uso rápido

1. **Anexe documentos** (PDF/DOCX/TXT) pelo clipe 📎 — viram base de conhecimento com embeddings
2. **Converse** no chat — a IA responde usando seus documentos (RAG)
3. **Escolha o modo** no seletor: Chat · FIRAC · Aula · Mapa mental · Questão · Flashcards
4. **🎧** ou clique no avatar **Naruto 🇧🇷** para ouvir a resposta (Kokoro TTS)
5. **⬇ PDF** exporta a conversa; **⬇** em cada resposta baixa o áudio WAV

---

## 🏗️ Estrutura do projeto

```
NeuralJuris/
├── docker-compose.yml          # backend + ollama
├── .env                        # segredos (NÃO commitar)
├── backend/
│   ├── Dockerfile              # Python 3.11 + tesseract + espeak-ng + torch CPU
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # app FastAPI, rotas, estáticos
│       ├── db.py               # SQLite (documentos, chunks, questões, editais, pesquisas)
│       ├── auth.py             # JWT
│       ├── static/             # interface web (index.html), mermaid, jsPDF, naruto.gif
│       ├── services/
│       │   ├── document.py     # extração PDF/DOCX/TXT + OCR (Tesseract)
│       │   ├── ollama.py       # chat, embeddings, busca web
│       │   ├── embeddings.py   # vetores via nomic-embed-text
│       │   ├── ocr.py          # OCR pt-BR
│       │   └── tts.py          # Kokoro TTS + segmentação + fallback espeak
│       ├── routers/
│       │   ├── documents.py    # upload, busca, listagem de documentos
│       │   ├── ask.py          # /ask — chat com RAG (+ pesquisa web opcional)
│       │   ├── questions.py    # banco de questões + estatísticas
│       │   ├── editais.py      # análise de editais (detecção de disciplinas)
│       │   ├── intelligence.py # FIRAC+, aulas, mapas mentais, questões, flashcards
│       │   ├── auth.py         # login JWT
│       │   └── tts.py          # /tts/generate, /tts/audio, /tts/voices
│       └── research/           # Research Engine
│           ├── crawler.py      # fetch com robots.txt + rate limit
│           ├── scraper.py      # extração de conteúdo de páginas
│           ├── search_engine.py# APIs oficiais (Planalto, Câmara, Senado, CNJ, STF, STJ, TJs)
│           ├── retriever.py    # busca híbrida local + web
│           ├── rag_engine.py   # pipeline pesquisa → resposta com citações
│           ├── citation_manager.py
│           └── routes.py       # /research/*
├── storage/                    # SQLite + uploads + cache TTS (gitignored)
├── models/                     # volumes Ollama (gitignored)
├── datasets/  legal/  training/  frontend/  docs/   # scaffolding para fases futuras
```

---

## 🧩 Funcionalidades

| Módulo | O que faz |
|---|---|
| 📄 Documentos | Upload PDF/DOCX/TXT/MD, OCR para digitalizados, dedup SHA-256, chunking + embeddings |
| 💬 Chat RAG | Respostas baseadas na sua base com fontes; flag 🌐 pesquisa na web |
| 🔬 Research Engine | Pesquisa em fontes oficiais (Planalto, STF, STJ, CNJ DataJud, TJs GO/TO/BA) com citações verificáveis |
| ⚖️ FIRAC+ | Análise jurídica estruturada: Fatos→Problema→Normas→Interpretação→Aplicação→Conclusão |
| ❓ Questões | Geração com JSON estruturado + **validação independente do gabarito** antes de salvar |
| 📖 Aulas | Aula completa: objetivo, conteúdo, pegadinhas, exemplos, resumo |
| 🧠 Mapas mentais | Diagramas Mermaid renderizados (da sua base de conhecimento) |
| 🃏 Flashcards | Cards clicáveis frente/verso |
| 🎧 TTS | **Kokoro-82M** neural pt-BR (vozes Alex/Santa/Dora), segmentos longos, player com progresso, download WAV; fallback espeak-ng |
| 🖼️ Avatar | Naruto 🇧🇷 animado (GIF), clique para play/pause |
| ⬇ PDF | Exporta conversa ou resposta individual (html2canvas + jsPDF, offline) |
| 🔐 Auth | JWT (12h) protege uploads/questões/editais |
| 📊 Estatísticas | Taxa de acerto por disciplina |

---

## 🔌 Principais endpoints

```
POST /documents/upload        # upload de documento (auth)
GET  /documents/search?q=     # busca na base
POST /ask                     # chat RAG {pergunta, estado, pesquisar_web}
POST /research/search         # busca em fontes oficiais
POST /research/analyze        # análise profunda com citações
GET  /research/history|sources
POST /intelligence/firac|aula|mapa-mental|questao|flashcards
POST /tts/generate            # {text, voice, speed} → segmentos WAV
GET  /tts/audio/{id}/{i}      # segmento de áudio
GET  /tts/audio/{id}/completo # WAV único p/ download
GET  /tts/voices              # vozes disponíveis
POST /auth/login              # {usuario, senha} → token
GET  /questions|stats         # banco de questões
POST /editais/upload          # análise de edital (auth)
```

---

## ⚙️ Stack

- **Backend**: Python 3.11, FastAPI, SQLite, JWT
- **IA**: Ollama (`llama3.2:1b` chat, `nomic-embed-text` embeddings)
- **TTS**: Kokoro-82M (torch CPU) + fallback espeak-ng
- **OCR**: Tesseract (`por`)
- **Frontend**: HTML/JS vanilla servido pelo backend (offline, libs vendorizadas)
- **Infra**: Docker Compose (backend `3g` + ollama `4g` RAM)

---

## 🧠 Notas e limitações

- **Modelo 1B**: rápido mas alucina detalhes jurídicos — as *fontes* são reais, a *redação* pode falhar. Para melhor qualidade, `ollama pull qwen2.5:3b` e ajuste `OLLAMA_MODEL`.
- **CPU-only**: tudo roda na CPU do notebook; respostas e síntese de áudio longas são lentas (use os indicadores ⏳).
- **TTS**: primeira síntese baixa o modelo Kokoro (~350 MB) uma vez; cache em `storage/tts` com limpeza >2h.
- **LGPD/direitos**: o Research Engine respeita robots.txt, rate limit e usa prioritariamente APIs oficiais; Vade Mecum comercial é só consulta — fontes oficiais prevalecem.
- **Não commitar**: `.env`, `storage/`, `models/` (ver `.gitignore`).

## 👤 Autor

Samuel Carlos Pereira — NeuralJuris AI
