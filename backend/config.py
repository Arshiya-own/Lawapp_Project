"""Configuration and binding constants.

Two kinds of value live here:

- `Settings` — secrets and paths, read from `.env`. Missing ones fail at import time
  rather than surfacing as a confusing 500 on the first request.
- Module constants — every number the specs bind. They are NOT environment variables
  on purpose: a dashboard typo must not be able to silently change the embedding
  dimensionality or swap the generation model.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent

# --- Models (04_ai_ml_spec.md §2, §5.1) -------------------------------------
# gemini-2.5-flash returns 404 "no longer available to new users" for keys created
# after its cutoff; Google's own error names gemini-3.6-flash as the migration
# target. Pinned, not `gemini-flash-latest`, so § 8 determinism holds. -> D-008
GENERATION_MODEL = "gemini-3.6-flash"
# text-embedding-004 was shut down 2026-01-14; gemini-embedding-001 keeps both the
# 768 dimensions and the parameter-based task types the spec's design assumes. -> D-003
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
GENERATION_TEMPERATURE = 0.2
EMBED_TASK_QUERY = "RETRIEVAL_QUERY"
EMBED_TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"

# --- Chunking (04_ai_ml_spec.md §3.2) ---------------------------------------
TOKENIZER_ENCODING = "cl100k_base"
CHUNK_TARGET_TOKENS = 400
CHUNK_MIN_TOKENS = 150
CHUNK_MAX_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 80
SENTENCE_BOUNDARY_WINDOW_TOKENS = 30

# --- Retrieval (04_ai_ml_spec.md §5.2) --------------------------------------
SIMILARITY_THRESHOLD = 0.65
OVER_RETRIEVAL_TOP_K = 20
FINAL_TOP_K_PER_DIMENSION = 5
SIMILARITY_PRECISION = 3

# --- Ranking (04_ai_ml_spec.md §6) ------------------------------------------
# court_tier ascending -> date descending -> similarity_score descending.
EXCLUDED_COURT_TIER = 4  # District courts, dropped before ranking

# --- Dimensions (03_backend_spec.md §5.4) -----------------------------------
DIMENSIONS_PER_CASE = 3  # exactly 3; re-prompt once, then error
DIMENSION_GENERATION_RETRIES = 1

# --- Snippets ---------------------------------------------------------------
SNIPPET_MAX_CHARS = 400
SNIPPET_BOUNDARY_SEARCH_CHARS = 50

# --- Upload (03_backend_spec.md §5.2) ---------------------------------------
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_UPLOAD_MIME = "application/pdf"

# --- OCR (03_backend_spec.md §7) --------------------------------------------
OCR_MIN_CHARS = 200  # below this -> 422 ocr_failed
PAGE_MARKER = "\n\n--- Page {n} ---\n\n"

# --- Contract formats (03_backend_spec.md §12) ------------------------------
# datetime.isoformat() emits "+00:00", which violates the contract. Always strftime.
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
API_PREFIX = "/api/v1"
CHUNK_ID_TEMPLATE = "{judgment_id}_chunk_{index:03d}"


class Settings(BaseSettings):
    """Secrets and paths from `.env` at the repository root."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env also carries VITE_* vars the frontend reads
    )

    # Google OAuth — the code exchange happens here, server-side, because Google's
    # "Web application" client type requires client_secret even under PKCE.
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    gemini_api_key: str

    jwt_signing_secret: str
    jwt_expiry_minutes: int = 60

    eval_token: str

    upload_dir: Path = Path("./var/uploads")
    sqlite_path: Path = Path("./var/lawapp.db")
    corpus_index_path: Path = Path("../data/corpus_index.json")

    frontend_base_url: str = "http://localhost:5173"

    def resolved(self, value: Path) -> Path:
        """Resolve a configured path against the repo root, not the process cwd."""
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @property
    def upload_path(self) -> Path:
        return self.resolved(self.upload_dir)

    @property
    def db_path(self) -> Path:
        return self.resolved(self.sqlite_path)

    @property
    def index_path(self) -> Path:
        return self.resolved(self.corpus_index_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
