from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.routers import ask, auth, documents, editais, intelligence, questions, tts
from app.research import routes as research_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="NeuralJuris AI",
    description="IA brasileira para concursos públicos de Goiás, Tocantins e Bahia",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(editais.router)
app.include_router(research_routes.router)
app.include_router(intelligence.router)
app.include_router(tts.router)


@app.get("/")
def home():
    return {
        "projeto": "NeuralJuris AI",
        "titular": "Samuel Carlos Pereira",
        "versao": "0.1.0",
        "status": "online",
        "foco": ["GO", "TO", "BA"],
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
