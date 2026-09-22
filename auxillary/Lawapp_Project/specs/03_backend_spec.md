# 03 — Backend Specification

**Document:** Backend / API Specification
**Version:** 1.0
**Audience:** Engineers implementing the Mini-JuriNex backend

---

## 1. Purpose

This document defines the HTTP API, data models, authentication flow, error model, and backend behaviors for Mini-JuriNex. The contract described here is binding: frontend code and our automated grading script both depend on exact field names, types, and HTTP status codes.

---

## 2. Tech Stack (Binding)

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| Framework | FastAPI |
| ASGI server | uvicorn |
| Data validation | Pydantic v2 |
| HTTP client (outbound) | httpx |
| Auth provider | Google OAuth 2.0 |
| Session model | JWT (Authorization: Bearer) **or** HTTP-only cookies — pick one |

Libraries permitted without justification: `google-generativeai`, `google-cloud-storage`, `pytesseract`, `pypdf`, `chromadb` or `faiss-cpu` or `pgvector`, `authlib` or `python-jose`, `httpx`, `pydantic`, `python-multipart`, `structlog`.

Other libraries are permitted but should be noted in `DEVIATIONS.md` with justification.

---

## 3. Base URL and Conventions

- Base path: `/api/v1`
- Content-Type: `application/json` for all request and response bodies (except multipart upload)
- All request bodies and response bodies are UTF-8 JSON
- All timestamps are ISO 8601 UTC with `Z` suffix (see `01_architecture.md` § 6)
- Field names are `snake_case`
- Pagination (if used in future): cursor-based; not needed for this exercise

---

## 4. Error Model

All error responses follow this shape:

```json
{
  "error": {
    "code": "string",
    "message": "human-readable message",
    "details": { "optional": "structured context" }
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `bad_request` | Malformed JSON, missing required fields |
| 401 | `unauthenticated` | No valid session / expired token |
| 403 | `forbidden` | Authenticated but not allowed (rare — prefer 404) |
| 404 | `not_found` | Resource does not exist, or user lacks access |
| 413 | `payload_too_large` | File exceeds 20 MB |
| 415 | `unsupported_media_type` | File is not `application/pdf` |
| 422 | `ocr_failed` | Uploaded PDF cannot be OCR'd (corrupted, image-only with illegible scan) |
| 422 | `validation_error` | Pydantic validation failed on request body |
| 429 | `rate_limited` | Too many requests (not required to implement, but document if you do) |
| 500 | `internal_error` | Unexpected server error |
| 502 | `upstream_error` | Gemini or GCS returned an error |

**Important:** OCR failures return **422**, not 400 or 500. This distinguishes a structurally valid PDF that happens to be unreadable from a malformed request.

---

## 5. Endpoints

### 5.1 Authentication

#### `GET /api/v1/auth/google/authorize`

Initiates OAuth. Returns the Google consent URL or redirects directly to it (implementer's choice).

**Query params:**
- `return_to` (optional): path to redirect to after successful auth. Default `/`.

**Response (if JSON):**
```json
{ "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth?..." }
```

#### `GET /api/v1/auth/google/callback`

OAuth callback. Exchanges code for tokens, creates session, redirects frontend.

**Query params:** `code`, `state` (from Google)

**Response:** 302 redirect to frontend with session established (cookie set OR `?token=JWT` query param — specify in your README which you chose).

#### `GET /api/v1/auth/me`

**Auth:** required

**Response 200:**
```json
{
  "user_id": "user_<uuid>",
  "email": "lawyer@example.com",
  "name": "Jane Doe",
  "picture": "https://lh3.googleusercontent.com/...",
  "created_at": "2026-04-19T14:30:00Z"
}
```

#### `POST /api/v1/auth/logout`

**Auth:** required
**Response 204:** no body. Clears session.

---

### 5.2 Cases — Upload

#### `POST /api/v1/cases/upload`

**Auth:** required
**Content-Type:** `multipart/form-data`
**Body:** field `file` — the PDF

**Success response 201:**
```json
{
  "case_id": "case_<uuidv4>",
  "status": "processing",
  "uploaded_at": "2026-04-19T14:30:00Z"
}
```

**Error responses:**
- 413 if file > 20 MB
- 415 if MIME type != `application/pdf`
- 422 with `code: "ocr_failed"` if OCR cannot extract any text

**Case ID format:** case IDs MUST be prefixed `case_` followed immediately by a UUIDv4 string (hex with hyphens, lowercase). Example: `case_a3f2b1e4-9c8d-4b7a-8e6f-1234567890ab`. Not acceptable: bare UUID, UUIDs without hyphens, other prefixes.

**Processing behavior:**
- Upload → GCS → OCR → metadata extraction happens synchronously in one request.
- The endpoint blocks until processing completes or fails.
- If it takes longer than 60 seconds, the response is 504 — but this should not happen for the sample PDFs provided.

---

### 5.3 Cases — Read

#### `GET /api/v1/cases/{case_id}`

**Auth:** required (only the owner can fetch)

**Response 200:**
```json
{
  "case_id": "case_a3f2b1e4-9c8d-4b7a-8e6f-1234567890ab",
  "user_id": "user_<uuid>",
  "status": "processed",
  "metadata": {
    "parties": "Rahul Kasat vs. State of Maharashtra",
    "court": "Supreme Court of India",
    "jurisdiction": "Criminal",
    "sections_invoked": ["IPC 120B", "IPC 302"],
    "synopsis": "SLP (Criminal) filed in Supreme Court challenging Bombay High Court's dismissal of regular bail for conviction under IPC 120B and 302."
  },
  "dimensions": null,
  "retrieval": null,
  "uploaded_at": "2026-04-19T14:30:00Z",
  "processed_at": "2026-04-19T14:30:42Z"
}
```

Values of `dimensions` and `retrieval` are `null` until the respective endpoints are called.

**404** if the case does not exist or is not owned by the authenticated user.

#### `GET /api/v1/cases` (list)

**Auth:** required

**Response 200:**
```json
{
  "cases": [
    { "case_id": "case_…", "parties": "…", "uploaded_at": "…Z" }
  ]
}
```

Ordered by `uploaded_at` descending. No pagination needed for this exercise.

---

### 5.4 Dimensions

#### `POST /api/v1/cases/{case_id}/dimensions`

**Auth:** required
**Body:** none
**Idempotent:** calling a second time regenerates dimensions and overwrites the previous set.

**Response 200:**
```json
{
  "case_id": "case_…",
  "dimensions": [
    {
      "dimension_number": 1,
      "query": "Non-compliance with Section 65B certificate for electronic evidence",
      "rationale": "The case involves electronic evidence whose admissibility depends on Section 65B compliance."
    },
    {
      "dimension_number": 2,
      "query": "FIR initially registered for accident later converted to murder investigation",
      "rationale": "..."
    },
    {
      "dimension_number": 3,
      "query": "Prosecution witness contradicting the established motive for murder",
      "rationale": "..."
    }
  ],
  "generated_at": "2026-04-19T14:31:00Z"
}
```

Exactly 3 dimensions. See `04_ai_ml_spec.md` for the generation prompt.

**Errors:** 404 if case not found, 422 if case is not yet `processed`.

---

### 5.5 Retrieval

#### `POST /api/v1/cases/{case_id}/retrieve`

**Auth:** required
**Body:** none. Uses the dimensions most recently generated for this case.
**Idempotent:** calling again re-runs retrieval.

**Response 200:**
```json
{
  "case_id": "case_…",
  "results": [
    {
      "dimension_number": 1,
      "query": "Non-compliance with Section 65B certificate for electronic evidence",
      "judgments": [
        {
          "judgment_id": "j_0007",
          "citation": "(2014) 10 SCC 473",
          "case_name": "Anvar P.V. vs P.K. Basheer",
          "court": "Supreme Court of India",
          "court_tier": 1,
          "date": "2014-09-18",
          "chunk_id": "j_0007_chunk_004",
          "snippet": "The court held that compliance with Section 65B(4) is a pre-condition…",
          "similarity_score": 0.842
        }
      ]
    }
  ],
  "retrieved_at": "2026-04-19T14:32:00Z"
}
```

Up to 5 judgments per dimension, ranked per `04_ai_ml_spec.md`.

**Errors:** 404 if case not found, 422 if dimensions have not been generated yet (`code: "dimensions_missing"`).

---

## 6. Request/Response Type Reference (Pydantic Sketches)

```python
from pydantic import BaseModel
from typing import Literal

class Metadata(BaseModel):
    parties: str
    court: str
    jurisdiction: Literal["Criminal", "Civil", "Constitutional", "Commercial", "Other"]
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
    court_tier: int        # 1=SC, 2=same-state HC, 3=other HC
    date: str              # ISO date, YYYY-MM-DD
    chunk_id: str
    snippet: str
    similarity_score: float  # rounded to 3 decimals

class DimensionResult(BaseModel):
    dimension_number: int
    query: str
    judgments: list[RankedJudgment]
```

---

## 7. OCR Pipeline (Backend Implementation Note)

Per `01_architecture.md` § 4.7, OCR is done via Document AI or pytesseract. The pipeline:

1. Download PDF from GCS (or use the uploaded bytes before GCS write).
2. Extract text per page.
3. Concatenate with page markers: `\n\n--- Page {n} ---\n\n`.
4. If extracted text length < 200 characters → treat as OCR failure, return 422.
5. Pass the text to the metadata extractor.

---

## 8. Background Jobs / Async

For this exercise, all processing is synchronous in the upload request. No Celery, no Cloud Tasks, no Pub/Sub. Keep it simple.

---

## 9. Indexing

Indexing the `judgments_corpus.json` is a one-time operation. Expose it as:

- A CLI command: `python -m backend.scripts.index_corpus`
- Or an admin endpoint `POST /api/v1/admin/reindex` protected by a static admin token from env var `ADMIN_TOKEN`

Either is acceptable. Not both required.

---

## 10. CORS

Allow only the frontend origin. Methods: `GET, POST, OPTIONS`. Headers: `Content-Type, Authorization`.

---

## 11. Testing (Minimal Expectations)

- Unit tests for the chunking function
- Unit tests for the court-hierarchy ranker
- At least one integration test that uploads the sample PDF and asserts the response shape

Pytest is the expected test runner. `make test` or `pytest` from the backend directory should run all tests.

---

## 12. Summary of Binding Contracts

| Item | Contract |
|---|---|
| Base path | `/api/v1` |
| Case ID format | `case_<uuidv4>` (lowercase, hyphenated) |
| User ID format | `user_<uuidv4>` |
| Judgment ID format | `j_XXXX` (as given in corpus) |
| Chunk ID format | `{judgment_id}_chunk_{NNN}` (3-digit zero-padded) |
| OCR failure | HTTP 422, code `ocr_failed` |
| Max dimensions | 3 |
| Max judgments per dimension | 5 |
| Similarity score | float rounded to 3 decimals |
| Timestamps | ISO 8601 UTC, `Z` suffix |
| Field naming | `snake_case` |
