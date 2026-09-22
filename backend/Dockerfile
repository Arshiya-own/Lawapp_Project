# Backend image for Render (D-002).
#
# Docker rather than Render's native Python runtime: `pytesseract` shells out to the
# `tesseract` binary and `pdf2image` to poppler's `pdftoppm`. Native environments block
# apt-get and OS-level installs, so the OCR fallback could not exist there at all.
#
# Build context is the REPOSITORY ROOT, not backend/, because the image needs
# data/corpus_index.json — the committed vectors that let a cold start run without a
# single embedding API call (D-005):
#
#     docker build -f backend/Dockerfile -t minijurinex-api .

FROM python:3.11-slim

# tesseract-ocr  -> pytesseract, the OCR fallback when a PDF has no text layer
# poppler-utils  -> pdf2image rasterising pages for that fallback
# Cleaning apt lists in the same layer keeps them out of the image.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        tesseract-ocr \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first so the dependency layer is cached across code-only changes.
# faiss-cpu and numpy are the slow wheels; re-resolving them on every push is wasteful.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/

# config.py resolves configured paths against the repository root (its own parent), so
# /app is the root and data/corpus_index.json lands where the vector store expects it.
WORKDIR /app/backend

# Render injects $PORT and it varies between deploys, so it cannot be baked in.
# Shell form on purpose: exec form would pass the literal string "$PORT".
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
