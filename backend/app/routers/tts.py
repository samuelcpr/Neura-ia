import logging
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services import tts as tts_service

log = logging.getLogger("neuraljuris.tts.routes")
router = APIRouter(prefix="/tts", tags=["tts"])

_ID_RE = re.compile(r"^[a-f0-9]{20}$")


class GerarRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    voice: str = "pm_alex"
    speed: float = Field(1.0, ge=0.5, le=2.0)


@router.post("/generate")
def gerar_audio(req: GerarRequest):
    """Sintetiza o texto em segmentos de áudio. Retorna id + URLs dos segmentos."""
    if req.voice not in tts_service.VOZES:
        raise HTTPException(400, f"Voz inválida. Disponíveis: {list(tts_service.VOZES)}")
    texto = req.text.strip()
    if not texto:
        raise HTTPException(400, "Texto vazio")

    audio_id = tts_service.id_para_texto(texto, req.voice)
    manifesto = tts_service.ler_manifesto(audio_id)
    if manifesto and manifesto.get("segmentos"):
        return {
            "id": audio_id,
            "voice": req.voice,
            "cached": True,
            "motor": manifesto.get("motor", "cache"),
            "segments": len(manifesto["segmentos"]),
            "durations": manifesto.get("durations", []),
            "urls": [f"/tts/audio/{audio_id}/{i}" for i in range(len(manifesto["segmentos"]))],
        }

    segmentos = tts_service.segmentar_texto(texto)
    if not segmentos:
        raise HTTPException(400, "Texto sem conteúdo falável")

    urls, motores, durations = [], set(), []
    try:
        for i, seg in enumerate(segmentos):
            wav, motor = tts_service.sintetizar_segmento(seg, req.voice, req.speed)
            motores.add(motor)
            (tts_service.TTS_DIR / f"{audio_id}_{i}.wav").write_bytes(wav)
            durations.append(round(tts_service.duracao_wav(wav), 2))
            urls.append(f"/tts/audio/{audio_id}/{i}")
    except Exception as e:  # noqa: BLE001
        log.exception("Falha na síntese TTS")
        raise HTTPException(500, f"Erro ao gerar áudio: {e}") from e

    tts_service.salvar_manifesto(audio_id, {
        "voice": req.voice,
        "speed": req.speed,
        "segmentos": segmentos,
        "durations": durations,
        "motor": "+".join(sorted(motores)),
    })
    tts_service.limpar_antigos()

    return {
        "id": audio_id,
        "voice": req.voice,
        "cached": False,
        "motor": "+".join(sorted(motores)),
        "segments": len(segmentos),
        "durations": durations,
        "urls": urls,
    }


@router.get("/voices")
def listar_vozes():
    return {
        "voices": [
            {"id": vid, "nome": nome, "padrao": vid == tts_service.VOZ_PADRAO}
            for vid, nome in tts_service.VOZES.items()
        ],
        "motor": "kokoro" if tts_service.kokoro_disponivel() else "espeak-ng",
    }


@router.get("/audio/{audio_id}")
def info_audio(audio_id: str):
    """Manifesto do áudio (segmentos, voz, motor)."""
    if not _ID_RE.match(audio_id):
        raise HTTPException(404, "Áudio não encontrado")
    m = tts_service.ler_manifesto(audio_id)
    if not m:
        raise HTTPException(404, "Áudio não encontrado")
    return {"id": audio_id, **{k: v for k, v in m.items() if k != "segmentos"},
            "segments": len(m.get("segmentos", []))}


@router.get("/audio/{audio_id}/completo")
def baixar_completo(audio_id: str):
    """Baixa todos os segmentos concatenados em um único arquivo WAV."""
    if not _ID_RE.match(audio_id):
        raise HTTPException(404, "Áudio não encontrado")
    m = tts_service.ler_manifesto(audio_id)
    if not m:
        raise HTTPException(404, "Áudio não encontrado")
    wavs = []
    for i in range(len(m.get("segmentos", []))):
        p = tts_service.caminho_segmento(audio_id, i)
        if not p:
            raise HTTPException(404, "Segmento não encontrado")
        wavs.append(p.read_bytes())
    return Response(
        content=tts_service.juntar_wavs(wavs),
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="naruto-{audio_id[:8]}.wav"'},
    )


@router.get("/audio/{audio_id}/{index}")
def baixar_segmento(audio_id: str, index: int):
    if not _ID_RE.match(audio_id) or index < 0:
        raise HTTPException(404, "Segmento não encontrado")
    caminho = tts_service.caminho_segmento(audio_id, index)
    if not caminho:
        raise HTTPException(404, "Segmento não encontrado")
    return Response(content=caminho.read_bytes(), media_type="audio/wav")


@router.delete("/audio/{audio_id}")
def remover_audio(audio_id: str):
    if not _ID_RE.match(audio_id):
        raise HTTPException(404, "Áudio não encontrado")
    removidos = 0
    for p in tts_service.TTS_DIR.glob(f"{audio_id}*"):
        p.unlink(missing_ok=True)
        removidos += 1
    return {"removido": removidos > 0}
