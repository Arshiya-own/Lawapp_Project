"""The eval harness endpoint (starter_repo/README.md).

`POST /api/v1/eval/retrieve` is not described in the four specs — its contract comes
from the starter README and the locked `eval/eval.py`, which calls it with
``{"query": ..., "top_k": 10}`` and scores precision@5, recall@10 and MRR over the
returned `judgment_id` order.

The README describes it as "raw retrieval results... no dimension generation, no
court-tier reranking. It exposes your retriever directly so we can evaluate it in
isolation from the ranking logic." Two consequences, both deliberate:

- the 0.65 threshold is **not** applied here (see QUESTIONS.md Q-005);
- `court_tier` is reported as stored in the corpus, not recomputed, because there is
  no uploaded case to define "same state" against.

Results are collapsed to one entry per judgment. The harness scores distinct
`judgment_id`s, so returning several chunks of the same judgment would spend top-k
slots on duplicates and understate recall.
"""

import secrets
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import get_settings
from middleware import AppError, log_event
from models.schemas import EvalJudgment, EvalRetrieveRequest, EvalRetrieveResponse
from services import embeddings
from services.ranker import collapse_to_judgments
from services.vector_store import get_store

router = APIRouter(prefix="/eval", tags=["eval"])

bearer_scheme = HTTPBearer(auto_error=False)


def eval_token_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    """Static bearer token, kept separate from OAuth so the harness needs no login."""
    if credentials is None or not credentials.credentials:
        raise AppError(401, "unauthenticated", "Authentication required.")
    # Constant-time compare: this token is long-lived and shared.
    if not secrets.compare_digest(credentials.credentials,
                                  get_settings().eval_token):
        raise AppError(401, "unauthenticated", "Invalid evaluation token.")


@router.post("/retrieve", response_model=EvalRetrieveResponse,
             dependencies=[Depends(eval_token_auth)])
def eval_retrieve(payload: EvalRetrieveRequest) -> EvalRetrieveResponse:
    store = get_store()
    if payload.top_k < 1:
        raise AppError(400, "bad_request", "top_k must be at least 1.")

    # Search the whole index, then collapse: the corpus is 72 chunks across 12
    # judgments, so a top-k over chunks could return far fewer distinct judgments.
    hits = store.search(embeddings.embed_query(payload.query), len(store))
    unique = collapse_to_judgments(hits)
    unique.sort(key=lambda h: h.similarity, reverse=True)

    judgments = [
        EvalJudgment(
            judgment_id=hit.judgment_id,
            similarity_score=hit.similarity,
            court_tier=hit.metadata.get("court_tier", 0),
            date=hit.metadata.get("date", ""),
        )
        for hit in unique[:payload.top_k]
    ]

    log_event(event="eval_retrieve", query_chars=len(payload.query),
              top_k=payload.top_k, returned=len(judgments))
    return EvalRetrieveResponse(judgments=judgments)
