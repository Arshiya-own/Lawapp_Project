"""Mini-JuriNex backend.

Completes the provided skeleton per `03_backend_spec.md`.

Run locally:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
from config import API_PREFIX, get_settings
from middleware import RequestLoggingMiddleware, log_event, register_error_handlers
from routers import auth, cases


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()  # fails fast here if a secret is missing
    db.init_db()
    log_event(event="startup", upload_dir=str(settings.upload_path),
              db_path=str(settings.db_path))
    yield


app = FastAPI(title="Mini-JuriNex API", version="1.0.0", lifespan=lifespan)

# § 11: frontend origin only, no wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_base_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(RequestLoggingMiddleware)
register_error_handlers(app)

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(cases.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
