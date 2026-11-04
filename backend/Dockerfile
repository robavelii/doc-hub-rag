FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# /models holds the local embedding/reranker models (LOCAL_MODEL_CACHE_DIR); a named
# volume mounted there inherits this ownership, so models download once per host.
RUN useradd --create-home --uid 10001 appuser && mkdir -p /models && chown -R appuser:appuser /app /models
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
