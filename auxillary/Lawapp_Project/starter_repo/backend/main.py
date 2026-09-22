"""
Mini-JuriNex Backend — Starter Skeleton

This is a minimal FastAPI skeleton. Candidates implement the endpoints per
03_backend_spec.md. The structure below is suggested but not binding.

Run locally:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Mini-JuriNex API", version="1.0.0")

# CORS — restrict to your frontend origin in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# TODO — implement endpoints per 03_backend_spec.md:
#
#   Auth:
#     GET    /api/v1/auth/google/authorize
#     GET    /api/v1/auth/google/callback
#     GET    /api/v1/auth/me
#     POST   /api/v1/auth/logout
#
#   Cases:
#     POST   /api/v1/cases/upload
#     GET    /api/v1/cases/{case_id}
#     GET    /api/v1/cases
#
#   Pipeline:
#     POST   /api/v1/cases/{case_id}/dimensions
#     POST   /api/v1/cases/{case_id}/retrieve
#
#   Eval (required for the locked eval.py script):
#     POST   /api/v1/eval/retrieve
#
# Suggested module structure:
#   routers/
#     auth.py
#     cases.py
#     eval.py
#   services/
#     ocr.py
#     gemini_client.py
#     chunker.py
#     vector_store.py
#     ranker.py
#   models/
#     schemas.py       ← Pydantic request/response models
#   scripts/
#     index_corpus.py  ← one-time indexing per 01_architecture.md § 8
