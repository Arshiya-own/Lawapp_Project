"""Pydantic v2 models mirroring 03_backend_spec.md.

The four core types (`Metadata`, `Dimension`, `RankedJudgment`, `DimensionResult`) are
transcribed from the §6 sketches. The response envelopes come from the endpoint
definitions in §5, which are more complete than the sketches.

Two contract rules are enforced here rather than in handlers, so no endpoint can get
them individually wrong:

- timestamps serialize as ``%Y-%m-%dT%H:%M:%SZ`` (§3) — `datetime.isoformat()` emits
  ``+00:00`` and would fail the contract;
- `similarity_score` is rounded to 3 decimals (§12).
"""

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, PlainSerializer, field_validator

from config import SIMILARITY_PRECISION, TIMESTAMP_FORMAT


def utc_z(value: datetime) -> str:
    """Format a datetime as ISO 8601 UTC with a ``Z`` suffix, no milliseconds."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime(TIMESTAMP_FORMAT)


def now_utc() -> datetime:
    """Naive UTC 'now' — the single source of timestamps across the app."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Serializes in both python and json modes so tests and handlers see the same string.
UtcZ = Annotated[datetime, PlainSerializer(utc_z, return_type=str, when_used="always")]

CaseStatus = Literal["processing", "processed"]
Jurisdiction = Literal["Criminal", "Civil", "Constitutional", "Commercial", "Other"]


# --- §6 core types ----------------------------------------------------------


class Metadata(BaseModel):
    parties: str
    court: str
    jurisdiction: Jurisdiction
    sections_invoked: list[str]
    synopsis: str


class Dimension(BaseModel):
    dimension_number: int  # 1, 2, or 3
    query: str
    rationale: str


class RankedJudgment(BaseModel):
    judgment_id: str
    citation: str
    case_name: str
    court: str
    court_tier: int  # 1=SC, 2=same-state HC, 3=other HC
    date: str  # ISO date, YYYY-MM-DD
    chunk_id: str
    snippet: str
    similarity_score: float  # rounded to 3 decimals

    @field_validator("similarity_score")
    @classmethod
    def _round_similarity(cls, value: float) -> float:
        return round(value, SIMILARITY_PRECISION)


class DimensionResult(BaseModel):
    dimension_number: int
    query: str
    judgments: list[RankedJudgment]


# --- §5.1 auth --------------------------------------------------------------


class AuthorizeResponse(BaseModel):
    authorize_url: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    picture: str
    created_at: UtcZ


# --- §5.2 upload ------------------------------------------------------------


class UploadResponse(BaseModel):
    case_id: str
    status: CaseStatus
    uploaded_at: UtcZ


# --- §5.3 case read ---------------------------------------------------------


class CaseDetailResponse(BaseModel):
    case_id: str
    user_id: str
    status: CaseStatus
    metadata: Optional[Metadata] = None
    dimensions: Optional[list[Dimension]] = None
    retrieval: Optional[list[DimensionResult]] = None
    uploaded_at: UtcZ
    processed_at: Optional[UtcZ] = None


class CaseListItem(BaseModel):
    case_id: str
    parties: str
    uploaded_at: UtcZ


class CaseListResponse(BaseModel):
    cases: list[CaseListItem]


# --- §5.4 dimensions --------------------------------------------------------


class DimensionsResponse(BaseModel):
    case_id: str
    dimensions: list[Dimension]
    generated_at: UtcZ


# --- §5.5 retrieval ---------------------------------------------------------


class RetrievalResponse(BaseModel):
    case_id: str
    results: list[DimensionResult]
    retrieved_at: UtcZ


# --- Eval harness (starter_repo/README.md) ----------------------------------
# Raw top-k across the whole corpus: no dimension generation, no court-tier rerank.


class EvalRetrieveRequest(BaseModel):
    query: str
    top_k: int = 10


class EvalJudgment(BaseModel):
    judgment_id: str
    similarity_score: float
    court_tier: int
    date: str

    @field_validator("similarity_score")
    @classmethod
    def _round_similarity(cls, value: float) -> float:
        return round(value, SIMILARITY_PRECISION)


class EvalRetrieveResponse(BaseModel):
    judgments: list[EvalJudgment]


# --- §4 error model ---------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
