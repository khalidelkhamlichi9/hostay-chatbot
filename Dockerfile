FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    python -m nltk.downloader -d /usr/local/share/nltk_data punkt punkt_tab stopwords wordnet

COPY . .

EXPOSE 8055

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8055"]
