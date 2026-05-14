FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    NLTK_DATA=/usr/local/share/nltk_data \
    CHATBOT_DB_PATH=/app/data/hostay_chatbot.db

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# ── Layer 1: ML deps (fastembed + ONNX Runtime — ~200 MB, cached on VPS) ──
COPY requirements-ml.txt .
RUN pip install -r requirements-ml.txt

# Pre-bake the multilingual ONNX model into the image (~90 MB quantised).
# Cold starts are instant — no download at runtime.
RUN mkdir -p /app/.cache/fastembed && \
    python -c "\
from fastembed import TextEmbedding; \
list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', \
cache_dir='/app/.cache/fastembed').embed(['warmup'])); \
print('fastembed model ready')"

# ── Layer 2: App deps (fast — only rebuilds when requirements.txt changes) ──
COPY requirements.txt .
RUN pip install -r requirements.txt && \
    python -m nltk.downloader -d /usr/local/share/nltk_data punkt punkt_tab

# ── Layer 3: Source code ──
COPY . .

RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /app --shell /sbin/nologin app && \
    mkdir -p /app/data /app/.cache/fastembed && \
    chown -R app:app /app

USER app

EXPOSE 8055

HEALTHCHECK --interval=30s --timeout=8s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8055/live || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8055", "--proxy-headers"]
