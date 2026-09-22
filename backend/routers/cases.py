"""Case upload and read endpoints (03_backend_spec.md § 5.2, § 5.3)."""

import json
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import ValidationError

import db
from config import ALLOWED_UPLOAD_MIME, MAX_UPLOAD_BYTES, OVER_RETRIEVAL_TOP_K
from middleware import AppError, log_event
from models.schemas import (
    CaseDetailResponse,
    CaseListItem,
    CaseListResponse,
    Dimension,
    DimensionResult,
    DimensionsResponse,
    Metadata,
    RetrievalResponse,
    UploadResponse,
    now_utc,
    utc_z,
)
from security import current_user
from services import embeddings, gemini_client, ocr, ranker, storage
from services.vector_store import get_store

router = APIRouter(prefix="/cases", tags=["cases"])


def _loads(value: Optional[str]):
    return json.loads(value) if value else None


def _case_detail(row: sqlite3.Row) -> CaseDetailResponse:
    return CaseDetailResponse(
        case_id=row["case_id"],
        user_id=row["user_id"],
        status=row["status"],
        metadata=_loads(row["metadata_json"]),
        dimensions=_loads(row["dimensions_json"]),
        retrieval=_loads(row["retrieval_json"]),
        uploaded_at=row["uploaded_at"],
        processed_at=row["processed_at"],
    )


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_case(file: UploadFile = File(...),
                      user: sqlite3.Row = Depends(current_user)) -> UploadResponse:
    """Upload -> store -> OCR -> metadata extraction, synchronously (§ 8)."""
    if file.content_type != ALLOWED_UPLOAD_MIME:
        raise AppError(415, "unsupported_media_type",
                       "Only PDF files are accepted.",
                       {"content_type": file.content_type})

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError(413, "payload_too_large",
                       "File too large. Maximum 20 MB.",
                       {"size_bytes": len(data), "max_bytes": MAX_UPLOAD_BYTES})

    user_id = user["user_id"]
    case_id = db.new_case_id()
    uploaded_at = utc_z(now_utc())
    pdf_path = storage.save_case_pdf(user_id, case_id, data)

    try:
        result = ocr.extract_text(data)
        if ocr.is_failure(result):
            raise AppError(
                422, "ocr_failed",
                "We couldn't extract text from this PDF. It may be corrupted or "
                "image-only with illegible scans.",
                {"characters_extracted": len(result.text.strip())},
            )

        extracted = gemini_client.extract_metadata(result.text)
        try:
            metadata = Metadata.model_validate(extracted)
        except ValidationError as exc:
            raise AppError(502, "upstream_error",
                           "Gemini returned metadata that does not match the schema.",
                           {"errors": json.loads(exc.json())})
    except Exception:
        # Nothing is persisted for a case that failed to process (QUESTIONS.md Q-001),
        # so the stored PDF would otherwise be orphaned.
        storage.delete_case_pdf(user_id, case_id)
        raise

    db.create_case(case_id, user_id, "processing", uploaded_at, str(pdf_path))
    db.set_case_processed(case_id, metadata.model_dump(), utc_z(now_utc()))
    log_event(event="case_processed", case_id=case_id, user_id=user_id,
              pages=result.pages_processed, ocr_method=result.method)

    # § 5.2 shows `"status": "processing"` in the 201 body even though § 8 makes
    # processing synchronous. The literal response shape wins. See QUESTIONS.md Q-003.
    return UploadResponse(case_id=case_id, status="processing", uploaded_at=uploaded_at)


@router.get("", response_model=CaseListResponse)
def list_cases(user: sqlite3.Row = Depends(current_user)) -> CaseListResponse:
    rows = db.list_cases(user["user_id"])
    items = []
    for row in rows:
        metadata = _loads(row["metadata_json"]) or {}
        items.append(CaseListItem(
            case_id=row["case_id"],
            parties=metadata.get("parties", ""),
            uploaded_at=row["uploaded_at"],
        ))
    return CaseListResponse(cases=items)


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: str,
             user: sqlite3.Row = Depends(current_user)) -> CaseDetailResponse:
    row = db.get_case(case_id, user["user_id"])
    if row is None:
        # 404 rather than 403 for another user's case (§ 11) — do not leak existence.
        raise AppError(404, "not_found", "Case not found.")
    return _case_detail(row)


@router.post("/{case_id}/dimensions", response_model=DimensionsResponse)
def generate_dimensions(case_id: str,
                        user: sqlite3.Row = Depends(current_user)) -> DimensionsResponse:
    """§ 5.4. Idempotent: a second call regenerates and overwrites."""
    row = db.get_case(case_id, user["user_id"])
    if row is None:
        raise AppError(404, "not_found", "Case not found.")
    if row["status"] != "processed":
        raise AppError(422, "validation_error",
                       "Case has not finished processing.",
                       {"status": row["status"]})

    metadata = _loads(row["metadata_json"])
    if not metadata:
        raise AppError(422, "validation_error", "Case has no extracted metadata.")

    dimensions = gemini_client.generate_dimensions(metadata)
    db.set_case_dimensions(case_id, dimensions)
    log_event(event="dimensions_generated", case_id=case_id,
              count=len(dimensions))

    return DimensionsResponse(
        case_id=case_id,
        dimensions=[Dimension.model_validate(d) for d in dimensions],
        generated_at=utc_z(now_utc()),
    )


@router.post("/{case_id}/retrieve", response_model=RetrievalResponse)
def retrieve(case_id: str,
             user: sqlite3.Row = Depends(current_user)) -> RetrievalResponse:
    """§ 5.5. Embeds each stored dimension, searches, ranks, returns up to 5 each."""
    row = db.get_case(case_id, user["user_id"])
    if row is None:
        raise AppError(404, "not_found", "Case not found.")

    dimensions = _loads(row["dimensions_json"])
    if not dimensions:
        raise AppError(422, "dimensions_missing",
                       "Dimensions have not been generated for this case.")

    metadata = _loads(row["metadata_json"]) or {}
    case_state = ranker.resolve_case_state(metadata.get("court"))
    store = get_store()

    results: list[DimensionResult] = []
    for dimension in dimensions:
        query = dimension["query"]
        # One embedding call per dimension (§ 7) — never per chunk. The similarity
        # maths below is local.
        hits = store.search(embeddings.embed_query(query), OVER_RETRIEVAL_TOP_K)
        ranked = ranker.rank(hits, case_state)
        results.append(DimensionResult(
            dimension_number=dimension["dimension_number"],
            query=query,
            judgments=[r.to_dict() for r in ranked],
        ))

    db.set_case_retrieval(case_id, [r.model_dump() for r in results])
    log_event(event="retrieval_completed", case_id=case_id,
              case_state=case_state,
              counts=[len(r.judgments) for r in results])

    return RetrievalResponse(case_id=case_id, results=results,
                             retrieved_at=utc_z(now_utc()))
