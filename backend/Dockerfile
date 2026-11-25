FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

# Torch CPU-only (sem CUDA) para o Kokoro TTS — bem menor que o wheel padrão
RUN pip install --upgrade pip \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r /app/requirements.txt

COPY app/ /app/app/

RUN mkdir -p /data/uploads /data/text

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
