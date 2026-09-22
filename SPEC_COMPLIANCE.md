# SPEC COMPLIANCE CHECKLIST

This is an honest checklist of what you built vs. what you skipped. Scored under "Documentation quality" (7 pts) and factored into "Specification adherence" (30 pts).

Fill in each row:
- ✅ = Done per spec
- ⚠️ = Done with a deviation (must have a D-NNN entry in `DEVIATIONS.md`)
- ❌ = Not done (state why in the Notes column — time, difficulty, etc.)

---

## 01 — Architecture (`01_architecture.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| A-01 | React 18 + TypeScript + Vite + Tailwind frontend | | |
| A-02 | FastAPI backend on Python 3.11 | | |
| A-03 | Google OAuth 2.0 with PKCE | | |
| A-04 | GCS for raw PDF storage with signed URLs | | |
| A-05 | Vector store (one of: Vertex / Chroma / pgvector / FAISS) | | Which did you use? |
| A-06 | `text-embedding-004` for embeddings | | |
| A-07 | `gemini-2.5-flash` for generation | | |
| A-08 | Timestamps in ISO 8601 UTC with `Z` suffix | | |
| A-09 | UUIDv4 IDs with per-entity prefixes | | |
| A-10 | Cloud Run deployment (backend) | | |
| A-11 | Secrets via env vars, nothing committed | | |
| A-12 | Request logging with method, path, status, latency, user_id | | |
| A-13 | CORS restricted to frontend origin | | |
| A-14 | File upload limit 20 MB, PDF only | | |
| A-15 | 404 (not 403) when user accesses another user's case | | |

## 02 — Frontend (`02_frontend_spec.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| F-01 | Routes: `/login`, `/`, `/cases/:caseId` | | |
| F-02 | Login page with Google sign-in button | | |
| F-03 | Upload page with drop zone, 20 MB / PDF validation | | |
| F-04 | Past cases list on Upload page | | |
| F-05 | Results page with CaseMetadataCard | | |
| F-06 | DimensionCard — 3 cards with query, rationale, ranked judgments | | |
| F-07 | JudgmentItem with citation, court, date, similarity pill | | |
| F-08 | JudgmentSnippetModal with ESC/backdrop/close button | | |
| F-09 | All four states (loading/empty/error/success) for every data-fetching component | | |
| F-10 | Empty state text verbatim: `"No precedents found for this dimension."` | | |
| F-11 | Similarity score displayed to 3 decimal places | | |
| F-12 | Auth redirect to `/login` on 401 | | |
| F-13 | Header with logo, user email, sign-out | | |
| F-14 | Responsive layout (mobile single-column, desktop max 1024 px) | | |
| F-15 | WCAG AA color contrast; keyboard navigation | | |
| F-16 | No API keys in frontend code | | |
| F-17 | No auth tokens in localStorage | | |

## 03 — Backend (`03_backend_spec.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| B-01 | Base path `/api/v1` | | |
| B-02 | `GET /auth/google/authorize` | | |
| B-03 | `GET /auth/google/callback` | | |
| B-04 | `GET /auth/me` | | |
| B-05 | `POST /auth/logout` | | |
| B-06 | `POST /cases/upload` with multipart | | |
| B-07 | `GET /cases/{case_id}` | | |
| B-08 | `GET /cases` (list) | | |
| B-09 | `POST /cases/{case_id}/dimensions` | | |
| B-10 | `POST /cases/{case_id}/retrieve` | | |
| B-11 | `POST /eval/retrieve` (required by eval.py) | | |
| B-12 | Case IDs prefixed `case_` + UUIDv4 | | |
| B-13 | Error envelope format `{ "error": { "code", "message", "details" } }` | | |
| B-14 | OCR failure returns HTTP 422 with code `ocr_failed` | | |
| B-15 | 413 for file > 20 MB | | |
| B-16 | 415 for non-PDF | | |
| B-17 | Pydantic v2 validation | | |
| B-18 | CORS with methods `GET, POST, OPTIONS` | | |
| B-19 | At least one integration test covering upload → metadata | | |
| B-20 | At least one unit test for chunking | | |
| B-21 | At least one unit test for ranker | | |

## 04 — AI/ML (`04_ai_ml_spec.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| M-01 | Embedding model: `text-embedding-004` (768d) | | |
| M-02 | Generation model: `gemini-2.5-flash` at temperature 0.2 | | |
| M-03 | Tokenizer: tiktoken `cl100k_base` | | |
| M-04 | Target chunk size 400 tokens, min 150, max 500 | | |
| M-05 | Chunk overlap exactly 80 tokens | | |
| M-06 | Sentence-boundary preference within ±30 tokens of target | | |
| M-07 | No overlap across section boundaries | | |
| M-08 | Chunk IDs: `{judgment_id}_chunk_NNN` with 3-digit zero-padded index | | |
| M-09 | Chunk metadata includes court, court_tier, date, jurisdiction, state | | |
| M-10 | Metadata extraction prompt per § 4.1 | | |
| M-11 | Dimension generation prompt per § 4.2, exactly 3 dimensions | | |
| M-12 | Re-prompt once on malformed dimension output | | |
| M-13 | Query embedding with task type `RETRIEVAL_QUERY` | | |
| M-14 | Document embedding with task type `RETRIEVAL_DOCUMENT` | | |
| M-15 | Over-retrieval top-20 before filtering | | |
| M-16 | Similarity threshold 0.65 | | |
| M-17 | Collapse chunks to judgments (keep highest-similarity chunk per judgment) | | |
| M-18 | Rank by court_tier ascending | | |
| M-19 | Tie-breaker 1: date descending | | |
| M-20 | Tie-breaker 2: similarity_score descending | | |
| M-21 | Exclude court_tier 4 (District Court) entirely | | |
| M-22 | Top 5 judgments per dimension | | |
| M-23 | Similarity rounded to 3 decimals in responses | | |
| M-24 | Snippet truncation at 400 chars with sentence-boundary preference | | |

---

## Summary

- **Total items:** 77
- **Done (✅):** ___
- **Deviated (⚠️):** ___
- **Skipped (❌):** ___

If you skipped something critical (e.g., dimension generation), explain at the top which foundational pieces are missing and what consequences that has for the rest of the system.
