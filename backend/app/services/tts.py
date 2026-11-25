"""Serviço de síntese de voz (TTS) com Kokoro-82M — execução 100% local.

Fallback: espeak-ng (voz robótica) caso o Kokoro falhe.
Textos longos são segmentados em blocos falados sequencialmente.
"""
import hashlib
import io
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("neuraljuris.tts")

VOZES = {
    "pm_alex": "Alex (masculina)",
    "pm_santa": "Santa (masculina)",
    "pf_dora": "Dora (feminina)",
}
VOZ_PADRAO = "pm_alex"

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
TTS_DIR = DATA_DIR / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)

RETENCAO_SEGUNDOS = 2 * 3600  # limpa áudios com mais de 2h
MAX_CARACTERES = 8000
MAX_SEGMENTOS = 30

_pipeline = None


def _get_pipeline():
    """Carrega o Kokoro preguiçosamente (pesado: torch + modelo ~350MB)."""
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline

        log.info("Carregando Kokoro TTS (lang pt)...")
        _pipeline = KPipeline(lang_code="p")
        log.info("Kokoro TTS pronto")
    return _pipeline


def kokoro_disponivel() -> bool:
    try:
        _get_pipeline()
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("Kokoro indisponível: %s", e)
        return False


def segmentar_texto(texto: str, max_len: int = 380) -> list[str]:
    """Divide o texto em segmentos faláveis sem cortar palavras."""
    texto = re.sub(r"```[\s\S]*?```", " ", texto)
    texto = re.sub(r"[#*`>\[\]()|]", " ", texto)
    texto = re.sub(r"https?://\S+", " link ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    partes = re.split(r"(?<=[.!?…])\s+|\n+", texto)
    segmentos, atual = [], ""
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if len(atual) + len(parte) + 1 <= max_len:
            atual = f"{atual} {parte}".strip()
            continue
        if atual:
            segmentos.append(atual)
        while len(parte) > max_len:
            corte = parte.rfind(" ", 0, max_len)
            if corte < max_len // 3:
                corte = max_len
            segmentos.append(parte[:corte].strip())
            parte = parte[corte:].strip()
        atual = parte
    if atual:
        segmentos.append(atual)
    return [s for s in segmentos if s][:MAX_SEGMENTOS]


def _sintetizar_kokoro(segmento: str, voz: str, velocidade: float) -> bytes:
    """Gera WAV (PCM 24kHz) de um segmento via Kokoro."""
    import soundfile as sf

    pipe = _get_pipeline()
    audios = []
    for _gs, _ps, audio in pipe(segmento, voice=voz, speed=velocidade):
        audios.append(audio)
    if not audios:
        raise RuntimeError("Kokoro não gerou áudio")
    audio = np.concatenate(audios) if len(audios) > 1 else audios[0]
    buf = io.BytesIO()
    sf.write(buf, audio, 24000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _sintetizar_espeak(segmento: str) -> bytes:
    """Fallback com espeak-ng (pt-br)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = tmp.name
    try:
        subprocess.run(
            ["espeak-ng", "-v", "pt-br", "-s", "170", "-w", path, segmento],
            check=True, timeout=120, capture_output=True,
        )
        return Path(path).read_bytes()
    finally:
        Path(path).unlink(missing_ok=True)


def sintetizar_segmento(segmento: str, voz: str, velocidade: float = 1.0) -> tuple[bytes, str]:
    """Retorna (wav_bytes, motor_usado)."""
    try:
        return _sintetizar_kokoro(segmento, voz, velocidade), "kokoro"
    except Exception as e:  # noqa: BLE001
        log.warning("Kokoro falhou (%s); usando espeak-ng", e)
        return _sintetizar_espeak(segmento), "espeak"


def id_para_texto(texto: str, voz: str) -> str:
    h = hashlib.sha256(f"{voz}|{texto}".encode()).hexdigest()
    return h[:20]


def manifesto_existe(audio_id: str) -> bool:
    return (TTS_DIR / f"{audio_id}.json").exists()


def salvar_manifesto(audio_id: str, dados: dict):
    import json

    (TTS_DIR / f"{audio_id}.json").write_text(json.dumps(dados, ensure_ascii=False))


def ler_manifesto(audio_id: str) -> dict | None:
    import json

    p = TTS_DIR / f"{audio_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def duracao_wav(wav: bytes) -> float:
    """Duração em segundos de um WAV PCM."""
    import wave

    with wave.open(io.BytesIO(wav)) as w:
        return w.getnframes() / float(w.getframerate())


def juntar_wavs(wavs: list[bytes]) -> bytes:
    """Concatena vários WAVs PCM mono no mesmo formato em um único WAV."""
    import wave

    if not wavs:
        return b""
    frames_out = io.BytesIO()
    with wave.open(io.BytesIO(wavs[0])) as w0:
        params = w0.getparams()
        with wave.open(frames_out, "wb") as out:
            out.setparams(params)
            for wav in wavs:
                with wave.open(io.BytesIO(wav)) as w:
                    out.writeframes(w.readframes(w.getnframes()))
    return frames_out.getvalue()


def caminho_segmento(audio_id: str, idx: int) -> Path | None:
    p = TTS_DIR / f"{audio_id}_{idx}.wav"
    return p if p.exists() else None


def limpar_antigos():
    """Remove áudios e manifestos mais antigos que RETENCAO_SEGUNDOS."""
    limite = time.time() - RETENCAO_SEGUNDOS
    for p in TTS_DIR.iterdir():
        try:
            if p.stat().st_mtime < limite:
                p.unlink(missing_ok=True)
        except OSError:
            pass
