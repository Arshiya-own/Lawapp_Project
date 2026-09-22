"""Embedding calls and L2 normalization (04_ai_ml_spec.md § 5.1).

**Normalization is not optional here.** `gemini-embedding-001` pre-normalizes only its
default 3072-dimension output. At `output_dimensionality=768` — the dimensionality § 2
binds — vectors come back un-normalized; measured on the live API, a typical norm is
≈0.568, not 1.0.

That matters because the retrieval design is cosine similarity (§ 5.2 step 1) implemented
as a FAISS inner-product index. Inner product equals cosine similarity *only on unit
vectors*. Skipping normalization would therefore mean:

  - the binding 0.65 threshold (§ 5.2 step 3) compares against a quantity that is not
    cosine similarity, so it filters essentially arbitrarily;
  - top-20 over-retrieval (step 2) biases toward high-magnitude vectors rather than
    semantically close ones.

Both failures are silent — retrieval still returns plausible-looking results — which is
why normalization lives in one place here and is applied on both the document and the
query side rather than being left to each caller.
"""

import time

import numpy as np
from google import genai
from google.genai import types

from config import (
    EMBED_TASK_DOCUMENT,
    EMBED_TASK_QUERY,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    get_settings,
)
from middleware import AppError, log_event

EMBED_RETRIES = 1  # § 9: "Embedding call fails -> retry once. Then raise 502."


def _client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Scale each row to unit length, leaving zero vectors untouched."""
    array = np.asarray(vectors, dtype=np.float32)
    single = array.ndim == 1
    if single:
        array = array.reshape(1, -1)

    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # a zero vector has no direction to preserve
    normalized = (array / norms).astype(np.float32)
    return normalized[0] if single else normalized


def _embed(texts: list[str], task_type: str) -> np.ndarray:
    """Call the embedding API once, with a single retry per § 9."""
    client = _client()
    config = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )

    last_error = None
    for attempt in range(EMBED_RETRIES + 1):
        started = time.perf_counter()
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL, contents=texts, config=config
            )
            log_event(
                event="gemini_call",
                model=EMBEDDING_MODEL,
                task_type=task_type,
                token_count_estimate=sum(len(t) for t in texts) // 4,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                count=len(texts),
                attempt=attempt,
            )
            vectors = np.array([e.values for e in response.embeddings], dtype=np.float32)
            if vectors.shape[1] != EMBEDDING_DIMENSIONS:
                raise AppError(502, "upstream_error",
                               "Embedding returned unexpected dimensionality.",
                               {"expected": EMBEDDING_DIMENSIONS,
                                "received": int(vectors.shape[1])})
            return l2_normalize(vectors)
        except AppError:
            raise
        except Exception as exc:
            last_error = exc
            log_event(event="embedding_failed", attempt=attempt, error=repr(exc))

    raise AppError(502, "upstream_error", "Embedding call failed after a retry.",
                   {"reason": repr(last_error)})


def embed_documents(texts: list[str]) -> np.ndarray:
    """Embed corpus chunks at index time (`RETRIEVAL_DOCUMENT`). Unit-length rows."""
    return _embed(texts, EMBED_TASK_DOCUMENT)


def embed_query(text: str) -> np.ndarray:
    """Embed one dimension query (`RETRIEVAL_QUERY`). Unit-length vector."""
    return _embed([text], EMBED_TASK_QUERY)[0]
